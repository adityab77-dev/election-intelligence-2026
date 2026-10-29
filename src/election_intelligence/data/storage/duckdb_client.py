"""Thin, well-behaved wrapper around a DuckDB connection.

The wrapper centralises connection management so the rest of the codebase never
touches ``duckdb.connect`` directly. This keeps configuration (path, threads,
read-only mode) in one place and makes the storage layer easy to mock in tests.

It is usable as a context manager::

    from election_intelligence.data.storage import DuckDBClient

    with DuckDBClient() as db:
        frame = db.query("SELECT 1 AS n")

Connection and query logic beyond these primitives is intentionally deferred.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from election_intelligence.config import get_settings
from election_intelligence.exceptions import StorageError
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    import duckdb
    import pandas as pd

logger = get_logger(__name__)


class DuckDBClient:
    """Manage a single DuckDB connection with sensible defaults."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        read_only: bool | None = None,
    ) -> None:
        settings = get_settings().database
        self._path = Path(path) if path is not None else settings.path
        self._read_only = settings.read_only if read_only is None else read_only
        self._threads = settings.threads
        self._connection: duckdb.DuckDBPyConnection | None = None

    @property
    def path(self) -> Path:
        """Filesystem path of the backing database file."""
        return self._path

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Open (or return the existing) DuckDB connection."""
        if self._connection is not None:
            return self._connection

        import duckdb

        # A read-only connection cannot create the file, so only ensure the
        # parent directory exists for writable connections.
        if not self._read_only:
            self._path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._connection = duckdb.connect(
                database=str(self._path),
                read_only=self._read_only,
                config={"threads": self._threads},
            )
        except duckdb.Error as exc:  # pragma: no cover - thin pass-through
            raise StorageError(f"failed to open DuckDB at {self._path}") from exc

        logger.debug("opened DuckDB connection at %s", self._path)
        return self._connection

    def query(self, sql: str, parameters: list[Any] | None = None) -> pd.DataFrame:
        """Run a SQL statement and return the result as a DataFrame."""
        connection = self.connect()
        try:
            return connection.execute(sql, parameters or []).df()
        except Exception as exc:  # pragma: no cover - thin pass-through
            raise StorageError("query execution failed") from exc

    def close(self) -> None:
        """Close the connection if it is open."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.debug("closed DuckDB connection at %s", self._path)

    def __enter__(self) -> DuckDBClient:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
