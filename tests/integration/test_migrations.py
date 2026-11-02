"""Integration tests for schema migrations."""

from __future__ import annotations

import pytest

pytest.importorskip("duckdb")

from election_intelligence.data.storage import Database  # noqa: E402

EXPECTED_TABLES = {
    "states",
    "senate_races",
    "candidates",
    "polls",
    "poll_aggregates",
    "state_forecasts",
    "simulation_runs",
    "simulation_results",
    "election_results",
}


@pytest.mark.integration
def test_initialize_creates_all_tables() -> None:
    db = Database()
    try:
        applied = db.migrate()
        assert applied == [1]
        assert EXPECTED_TABLES <= db.table_names()
    finally:
        db.close()


@pytest.mark.integration
def test_migrations_are_idempotent() -> None:
    db = Database()
    try:
        db.migrate()
        before = db.migrator.applied_versions()
        # Re-running applies nothing new.
        assert db.migrate() == []
        assert db.migrator.applied_versions() == before
    finally:
        db.close()


@pytest.mark.integration
def test_schema_migrations_recorded() -> None:
    db = Database()
    try:
        db.migrate()
        rows = db.client.fetch_all("SELECT version, name FROM schema_migrations")
        assert any(r["name"] == "initial_schema" for r in rows)
    finally:
        db.close()
