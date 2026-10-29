"""Integration tests for the DuckDB client.

Marked ``integration`` because they open a real (temp-file) DuckDB database.
"""

from __future__ import annotations

import pytest

from election_intelligence.data.storage import DuckDBClient

pytest.importorskip("duckdb")


@pytest.mark.integration
def test_query_returns_dataframe() -> None:
    with DuckDBClient() as db:
        frame = db.query("SELECT 42 AS answer")
    assert frame.loc[0, "answer"] == 42


@pytest.mark.integration
def test_database_file_is_created() -> None:
    with DuckDBClient() as db:
        db.query("CREATE TABLE t (id INTEGER)")
        assert db.path.exists()
