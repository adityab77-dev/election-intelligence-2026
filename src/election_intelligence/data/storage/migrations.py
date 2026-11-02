"""Forward-only SQL migration runner.

Migration strategy (deliberately minimal, DuckDB-only, no external tooling):

- Each migration is a file ``migrations/NNNN_name.sql`` (zero-padded version).
- A ``schema_migrations`` table records which versions have been applied.
- :meth:`Migrator.apply_all` runs every pending migration, in version order,
  each inside its own transaction, and records it on success.

Migrations are forward-only: to change the schema, add a new file rather than
editing an applied one. Re-running is safe (idempotent) — already-applied
versions are skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from election_intelligence.exceptions import StorageError
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from election_intelligence.data.storage.duckdb_client import DuckDBClient

logger = get_logger(__name__)

DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_FILENAME_RE = re.compile(r"^(\d+)_(.+)\.sql$")


@dataclass(frozen=True)
class Migration:
    """A single discovered migration file."""

    version: int
    name: str
    path: Path


def _split_statements(script: str) -> list[str]:
    """Split a SQL script into individual statements.

    Full-line ``--`` comments are dropped; statements are split on ``;``. The
    project's DDL contains no semicolons inside string literals, so this simple
    splitter is sufficient (inline ``--`` comments are left for DuckDB to parse).
    """
    kept = [
        line for line in script.splitlines() if not line.strip().startswith("--")
    ]
    joined = "\n".join(kept)
    return [stmt.strip() for stmt in joined.split(";") if stmt.strip()]


class Migrator:
    """Discovers and applies forward-only SQL migrations."""

    def __init__(
        self, client: DuckDBClient, migrations_dir: Path | None = None
    ) -> None:
        self._client = client
        self._dir = migrations_dir or DEFAULT_MIGRATIONS_DIR

    def _ensure_tracking_table(self) -> None:
        self._client.run(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "    version INTEGER PRIMARY KEY,"
            "    name VARCHAR NOT NULL,"
            "    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            ")"
        )

    def applied_versions(self) -> set[int]:
        self._ensure_tracking_table()
        rows = self._client.fetch_all("SELECT version FROM schema_migrations")
        return {int(r["version"]) for r in rows}

    def discover(self) -> list[Migration]:
        if not self._dir.is_dir():
            raise StorageError(f"migrations directory not found: {self._dir}")
        migrations: list[Migration] = []
        for path in sorted(self._dir.glob("*.sql")):
            match = _FILENAME_RE.match(path.name)
            if not match:
                continue
            migrations.append(
                Migration(int(match.group(1)), match.group(2), path)
            )
        migrations.sort(key=lambda m: m.version)
        return migrations

    def apply_all(self) -> list[int]:
        """Apply every pending migration; return the versions applied now."""
        applied = self.applied_versions()
        newly_applied: list[int] = []
        for migration in self.discover():
            if migration.version in applied:
                continue
            self._apply(migration)
            newly_applied.append(migration.version)
        return newly_applied

    def _apply(self, migration: Migration) -> None:
        statements = _split_statements(migration.path.read_text(encoding="utf-8"))
        logger.info(
            "applying migration %04d_%s (%d statements)",
            migration.version,
            migration.name,
            len(statements),
        )
        try:
            with self._client.transaction() as conn:
                for statement in statements:
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    [migration.version, migration.name],
                )
        except Exception as exc:
            raise StorageError(
                f"migration {migration.version}_{migration.name} failed"
            ) from exc


__all__ = ["Migration", "Migrator", "DEFAULT_MIGRATIONS_DIR"]
