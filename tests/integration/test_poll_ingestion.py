"""Integration tests for the Phase 3 polling ingestion pipeline.

Covers the MVP output target: load polling data, then query the latest
polling average for Georgia, North Carolina, and Texas.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

pytest.importorskip("duckdb")

from election_intelligence.data.ingestion.polls import (  # noqa: E402
    PollIngestor,
    latest_poll,
    simple_polling_average,
)
from election_intelligence.data.storage import Database, SeedLoader  # noqa: E402
from election_intelligence.data.storage.entities import Poll  # noqa: E402


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database()
    database.migrate()
    SeedLoader(database).load_all()  # states + races (FK parents for polls)
    yield database
    database.close()


@pytest.mark.integration
def test_sample_polls_ingest_cleanly(db: Database) -> None:
    report = PollIngestor(db).ingest_file()
    assert report.ingested == 40
    assert report.rejected == 0
    assert db.polls.count() == 40


@pytest.mark.integration
def test_ingestion_is_idempotent(db: Database) -> None:
    ingestor = PollIngestor(db)
    ingestor.ingest_file()
    ingestor.ingest_file()  # deterministic ids -> upsert, no duplicates
    assert db.polls.count() == 40


@pytest.mark.integration
def test_mvp_output_target_latest_averages(db: Database) -> None:
    PollIngestor(db).ingest_file()

    # Windowed (last 21 days -> the three most recent polls per race).
    georgia = simple_polling_average(db, "GA-2026", window_days=21)
    north_carolina = simple_polling_average(db, "NC-2026", window_days=21)
    texas = simple_polling_average(db, "TX-2026", window_days=21)

    assert georgia is not None and georgia.n_polls == 3
    assert georgia.mean_margin_dem_minus_rep == pytest.approx(2.0)
    assert north_carolina.mean_margin_dem_minus_rep == pytest.approx(3.0)
    assert texas.mean_margin_dem_minus_rep == pytest.approx(-2.6667, abs=1e-3)


@pytest.mark.integration
def test_full_window_average_uses_all_polls(db: Database) -> None:
    PollIngestor(db).ingest_file()
    georgia = simple_polling_average(db, "GA-2026", window_days=None)
    assert georgia is not None
    assert georgia.n_polls == 5
    assert georgia.mean_margin_dem_minus_rep == pytest.approx(1.5)


@pytest.mark.integration
def test_latest_poll_is_most_recent(db: Database) -> None:
    PollIngestor(db).ingest_file()
    poll = latest_poll(db, "GA-2026")
    assert poll is not None
    assert poll.field_end == date(2026, 10, 29)
    assert poll.margin_dem_minus_rep == pytest.approx(2.5)


@pytest.mark.integration
def test_average_is_none_when_no_polls(db: Database) -> None:
    assert simple_polling_average(db, "GA-2026") is None


@pytest.mark.integration
def test_invalid_polls_are_rejected_not_stored(db: Database) -> None:
    polls = [
        Poll(race_id="CA-2026", pollster="X", field_end=date(2026, 10, 1),
             margin_dem_minus_rep=1.0),  # not a battleground
        Poll(race_id="GA-2026", pollster="Y", field_end=date(2026, 11, 20),
             margin_dem_minus_rep=1.0),  # after election day
        Poll(race_id="GA-2026", pollster="Z", field_end=date(2026, 10, 1),
             margin_dem_minus_rep=0.5),  # valid
    ]
    report = PollIngestor(db).ingest(polls)
    assert report.ingested == 1
    assert report.rejected == 2
    assert db.polls.count() == 1
