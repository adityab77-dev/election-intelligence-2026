"""Integration tests for the aggregation engine against DuckDB."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("duckdb")

from election_intelligence.aggregation import PollAggregator  # noqa: E402
from election_intelligence.data.ingestion.polls import PollIngestor  # noqa: E402
from election_intelligence.data.storage import Database, SeedLoader  # noqa: E402


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database()
    database.migrate()
    SeedLoader(database).load_all()
    PollIngestor(database).ingest_file()
    yield database
    database.close()


@pytest.mark.integration
def test_aggregate_race_reads_polls_and_weights(db: Database) -> None:
    result = PollAggregator().aggregate_race(db, "GA-2026")
    assert result is not None
    assert result.state_code == "GA"
    assert result.poll_count == 5
    assert result.std_error > 0.0
    # Recency weighting pulls toward the newer (higher) GA margins, so the
    # weighted margin exceeds the simple mean of 1.5.
    assert 1.6 < result.margin < 2.1
    assert sum(c.weight_share for c in result.contributions) == pytest.approx(1.0)


@pytest.mark.integration
def test_newest_poll_has_largest_share(db: Database) -> None:
    result = PollAggregator().aggregate_race(db, "GA-2026")
    top = result.contributions[0]  # sorted by weight_share desc
    assert top.field_end == max(c.field_end for c in result.contributions)


@pytest.mark.integration
def test_persist_and_latest_for_race_roundtrip(db: Database) -> None:
    aggregator = PollAggregator()
    result = aggregator.aggregate_race(db, "NC-2026")
    aggregator.persist(db, result)

    stored = db.poll_aggregates.latest_for_race("NC-2026")
    assert stored is not None
    assert stored.mean_margin == pytest.approx(result.margin)
    assert stored.n_polls == result.poll_count
    assert stored.method == "weighted_v1"


@pytest.mark.integration
def test_persist_is_idempotent(db: Database) -> None:
    aggregator = PollAggregator()
    result = aggregator.aggregate_race(db, "TX-2026")
    aggregator.persist(db, result)
    aggregator.persist(db, result)  # deterministic id -> upsert
    assert len(db.poll_aggregates.list_by_race("TX-2026")) == 1
