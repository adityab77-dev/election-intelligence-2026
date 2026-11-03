"""Integration test for the dashboard's read-only data layer.

Exercises _load_data end to end (without streamlit): populate the database via
the pipeline, then confirm the dashboard reads a coherent snapshot back.
"""

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("duckdb")
pytest.importorskip("numpy")

from election_intelligence.dashboard.app import _load_data  # noqa: E402
from election_intelligence.data.ingestion.polls import (  # noqa: E402
    BATTLEGROUND_RACES,
    PollIngestor,
)
from election_intelligence.data.storage import Database, SeedLoader  # noqa: E402
from election_intelligence.forecast import ForecastEngine  # noqa: E402
from election_intelligence.simulate import MonteCarloEngine, SimulationConfig  # noqa: E402

FD = date(2026, 11, 1)


@pytest.mark.integration
def test_load_data_after_full_pipeline() -> None:
    # Populate (read-write), then close so the dashboard can open read-only.
    db = Database()
    db.migrate()
    SeedLoader(db).load_all()
    PollIngestor(db).ingest_file()

    engine = ForecastEngine()
    forecasts = []
    for code, race_id in BATTLEGROUND_RACES.items():
        forecast = engine.forecast_race(db, race_id, state_code=code, forecast_date=FD)
        engine.persist(db, forecast)
        forecasts.append(forecast)

    MonteCarloEngine(SimulationConfig(n_simulations=5_000, random_seed=7)).run_and_store(
        db, forecasts
    )
    db.close()

    data = _load_data()
    assert data["error"] is None
    assert data["run"] is not None
    assert data["result"] is not None
    assert data["result"].prob_rep_control + data["result"].prob_dem_control == pytest.approx(1.0)
    assert len(data["forecasts"]) == len(BATTLEGROUND_RACES)
    assert len(data["aggregates"]) == len(BATTLEGROUND_RACES)
    assert data["polls_loaded"] == 40


@pytest.mark.integration
def test_load_data_without_simulation_is_graceful() -> None:
    db = Database()
    db.migrate()
    SeedLoader(db).load_all()
    PollIngestor(db).ingest_file()
    db.close()

    data = _load_data()
    # No simulation run yet, but no error and aggregates still available.
    assert data["error"] is None
    assert data["run"] is None
    assert data["result"] is None
    assert len(data["aggregates"]) == len(BATTLEGROUND_RACES)
