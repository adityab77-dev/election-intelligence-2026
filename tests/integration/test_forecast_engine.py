"""Integration tests for the forecast engine against DuckDB.

Covers the Phase 5 success criterion: generate forecasts for all eight
battleground states, store them, and read them back.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

pytest.importorskip("duckdb")

from election_intelligence.data.ingestion.polls import (  # noqa: E402
    BATTLEGROUND_RACES,
    PollIngestor,
)
from election_intelligence.data.storage import Database, SeedLoader  # noqa: E402
from election_intelligence.data.storage.entities import ConfidenceLevel  # noqa: E402
from election_intelligence.forecast import ForecastEngine  # noqa: E402

FD = date(2026, 11, 1)


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database()
    database.migrate()
    SeedLoader(database).load_all()
    PollIngestor(database).ingest_file()
    yield database
    database.close()


@pytest.mark.integration
def test_forecasts_generated_for_all_battlegrounds(db: Database) -> None:
    engine = ForecastEngine()
    for code, race_id in BATTLEGROUND_RACES.items():
        forecast = engine.forecast_race(db, race_id, state_code=code, forecast_date=FD)
        assert forecast is not None, code
        assert forecast.state_code == code
        assert forecast.sigma > 0.0
        assert forecast.poll_count == 5


@pytest.mark.integration
def test_georgia_matches_example_output(db: Database) -> None:
    forecast = ForecastEngine().forecast_race(
        db, "GA-2026", state_code="GA", forecast_date=FD
    )
    assert forecast is not None
    # Example: D +1.8, sigma ~3.9, confidence Medium.
    assert 1.6 < forecast.mean_margin < 2.1
    assert 3.5 < forecast.sigma < 4.5
    assert forecast.confidence_level is ConfidenceLevel.MEDIUM


@pytest.mark.integration
def test_persist_and_latest_for_race(db: Database) -> None:
    engine = ForecastEngine()
    forecast = engine.forecast_race(db, "NC-2026", state_code="NC", forecast_date=FD)
    engine.persist(db, forecast)

    stored = db.state_forecasts.latest_for_race("NC-2026")
    assert stored is not None
    assert stored.mean_margin == pytest.approx(forecast.mean_margin)
    assert stored.sigma == pytest.approx(forecast.sigma)
    assert stored.confidence_level == forecast.confidence_level


@pytest.mark.integration
def test_persist_is_idempotent(db: Database) -> None:
    engine = ForecastEngine()
    forecast = engine.forecast_race(db, "TX-2026", state_code="TX", forecast_date=FD)
    engine.persist(db, forecast)
    engine.persist(db, forecast)  # deterministic id -> upsert
    assert len(db.state_forecasts.list_by_race("TX-2026")) == 1


@pytest.mark.integration
def test_forecast_is_reproducible_end_to_end(db: Database) -> None:
    engine = ForecastEngine()
    first = engine.forecast_race(db, "IA-2026", state_code="IA", forecast_date=FD)
    second = engine.forecast_race(db, "IA-2026", state_code="IA", forecast_date=FD)
    assert first.inputs_hash == second.inputs_hash
    assert first.sigma == pytest.approx(second.sigma)
    assert first.mean_margin == pytest.approx(second.mean_margin)


@pytest.mark.integration
def test_no_polls_yields_no_forecast(db: Database) -> None:
    # Clear polls for a race and confirm None.
    db.client.run("DELETE FROM polls WHERE race_id = ?", ["ME-2026"])
    assert ForecastEngine().forecast_race(db, "ME-2026", state_code="ME") is None
