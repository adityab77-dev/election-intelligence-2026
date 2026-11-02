"""Integration tests for the Monte Carlo engine with DuckDB persistence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

pytest.importorskip("duckdb")
pytest.importorskip("numpy")

from election_intelligence.data.ingestion.polls import (  # noqa: E402
    BATTLEGROUND_RACES,
    PollIngestor,
)
from election_intelligence.data.storage import Database, SeedLoader  # noqa: E402
from election_intelligence.forecast import ForecastEngine  # noqa: E402
from election_intelligence.simulate import MonteCarloEngine, SimulationConfig  # noqa: E402

FD = date(2026, 11, 1)
CONFIG = SimulationConfig(n_simulations=20_000, random_seed=7)


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database()
    database.migrate()
    SeedLoader(database).load_all()
    PollIngestor(database).ingest_file()
    yield database
    database.close()


def _battleground_forecasts(db: Database) -> list:
    engine = ForecastEngine()
    return [
        engine.forecast_race(db, race_id, state_code=code, forecast_date=FD)
        for code, race_id in BATTLEGROUND_RACES.items()
    ]


@pytest.mark.integration
def test_run_and_store_persists_run_and_result(db: Database) -> None:
    output = MonteCarloEngine(CONFIG).run_and_store(
        db, _battleground_forecasts(db), code_version="testsha"
    )

    run = db.simulation_runs.get(output.run_id)
    assert run is not None
    assert run.n_simulations == 20_000
    assert run.random_seed == 7
    assert run.code_version == "testsha"

    result = db.simulation_results.get(output.run_id)
    assert result is not None
    assert result.prob_rep_control == pytest.approx(output.prob_rep_control)
    assert result.expected_rep_seats == pytest.approx(output.expected_rep_seats)
    assert result.influential_states is not None
    assert result.seat_histogram is not None


@pytest.mark.integration
def test_probabilities_and_seats_consistent(db: Database) -> None:
    output = MonteCarloEngine(CONFIG).simulate(_battleground_forecasts(db))
    assert output.prob_rep_control + output.prob_dem_control == pytest.approx(1.0)
    assert output.expected_rep_seats + output.expected_dem_seats == pytest.approx(100.0)
    # Synthetic sample data favours Republicans (TX/OH/IA lean R).
    assert output.prob_rep_control > 0.5


@pytest.mark.integration
def test_reproducible_end_to_end(db: Database) -> None:
    forecasts = _battleground_forecasts(db)
    a = MonteCarloEngine(CONFIG).simulate(forecasts)
    b = MonteCarloEngine(CONFIG).simulate(forecasts)
    assert a.prob_rep_control == b.prob_rep_control
    assert a.inputs_hash == b.inputs_hash


@pytest.mark.integration
def test_latest_run_retrievable(db: Database) -> None:
    MonteCarloEngine(CONFIG).run_and_store(db, _battleground_forecasts(db))
    latest = db.simulation_runs.latest()
    assert latest is not None
    assert latest.status.value == "completed"


@pytest.mark.integration
def test_store_is_idempotent(db: Database) -> None:
    forecasts = _battleground_forecasts(db)
    engine = MonteCarloEngine(CONFIG)
    engine.run_and_store(db, forecasts)
    engine.run_and_store(db, forecasts)  # same inputs -> same run_id -> upsert
    assert db.simulation_runs.count() == 1
    assert db.simulation_results.count() == 1
