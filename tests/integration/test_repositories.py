"""Integration tests for the repository layer (CRUD, FK integrity, JSON)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timezone

import pytest

pytest.importorskip("duckdb")

from election_intelligence.data.storage import Database  # noqa: E402
from election_intelligence.data.storage.entities import (  # noqa: E402
    Candidate,
    ConfidenceLevel,
    ElectionResult,
    Poll,
    SenateRace,
    SimulationResult,
    SimulationRun,
    State,
    StateForecast,
)
from election_intelligence.exceptions import StorageError  # noqa: E402


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database()
    database.migrate()
    yield database
    database.close()


def _seed_race(db: Database) -> None:
    db.states.insert(State(state_code="TX", name="Texas", time_zone="America/Chicago"))
    db.senate_races.insert(SenateRace(race_id="TX-2026", state_code="TX"))


@pytest.mark.integration
def test_state_crud_lifecycle(db: Database) -> None:
    db.states.insert(State(state_code="OH", name="Ohio", time_zone="America/New_York"))
    assert db.states.get("OH").name == "Ohio"
    assert db.states.count() == 1

    # upsert updates in place (no duplicate row).
    db.states.upsert(
        State(state_code="OH", name="Ohio (updated)", time_zone="America/New_York")
    )
    assert db.states.count() == 1
    assert db.states.get("OH").name == "Ohio (updated)"

    assert db.states.delete("OH") is True
    assert db.states.get("OH") is None
    assert db.states.delete("OH") is False


@pytest.mark.integration
def test_foreign_key_chain(db: Database) -> None:
    _seed_race(db)
    db.candidates.insert(
        Candidate(candidate_id="c-tx-1", race_id="TX-2026", name="Jane Doe", party="DEM")
    )
    db.polls.insert(
        Poll(
            race_id="TX-2026",
            pollster="Example Poll",
            field_end=date(2026, 10, 20),
            margin_dem_minus_rep=-2.5,
            population="LV",
        )
    )
    assert len(db.candidates.list_by_race("TX-2026")) == 1
    assert len(db.polls.list_by_race("TX-2026")) == 1


@pytest.mark.integration
def test_foreign_key_violation_is_rejected(db: Database) -> None:
    # No parent race exists -> insert must fail.
    with pytest.raises(StorageError):
        db.candidates.insert(
            Candidate(
                candidate_id="orphan", race_id="DOES-NOT-EXIST", name="X", party="REP"
            )
        )


@pytest.mark.integration
def test_state_forecast_crud(db: Database) -> None:
    from datetime import date

    _seed_race(db)
    forecast = StateForecast(
        race_id="TX-2026",
        state_code="TX",
        mean_margin=-2.0,
        sigma=3.8,
        confidence_level="Medium",
        poll_count=5,
        forecast_date=date(2026, 11, 1),
        inputs_hash="abc123",
    )
    db.state_forecasts.insert(forecast)

    stored = db.state_forecasts.get(forecast.forecast_id)
    assert stored is not None
    assert stored.mean_margin == pytest.approx(-2.0)
    assert stored.sigma == pytest.approx(3.8)
    assert stored.confidence_level is ConfidenceLevel.MEDIUM
    assert len(db.state_forecasts.list_by_race("TX-2026")) == 1


@pytest.mark.integration
def test_simulation_run_and_result_reproducibility_fields(db: Database) -> None:
    run = SimulationRun(
        regime="live",
        n_simulations=100_000,
        random_seed=12345,
        inputs_hash="deadbeef",
        code_version="abc123",
    )
    db.simulation_runs.insert(run)
    db.simulation_results.insert(
        SimulationResult(
            run_id=run.run_id,
            prob_rep_control=0.61,
            prob_dem_control=0.39,
            rep_seats_median=51,
            seat_histogram={"50": 0.1, "51": 0.3},
            paths=[["TX", "OH"], ["IA"]],
        )
    )
    fetched_run = db.simulation_runs.get(run.run_id)
    assert fetched_run.random_seed == 12345
    assert fetched_run.inputs_hash == "deadbeef"
    assert fetched_run.code_version == "abc123"

    result = db.simulation_results.get(run.run_id)
    assert result.prob_rep_control == pytest.approx(0.61)
    assert result.seat_histogram == {"50": 0.1, "51": 0.3}
    assert result.paths == [["TX", "OH"], ["IA"]]


@pytest.mark.integration
def test_election_result_insert_and_query(db: Database) -> None:
    _seed_race(db)
    db.candidates.insert(
        Candidate(candidate_id="c-tx-1", race_id="TX-2026", name="Jane Doe", party="DEM")
    )
    db.election_results.insert(
        ElectionResult(
            race_id="TX-2026",
            candidate_id="c-tx-1",
            votes=12_345,
            pct_expected_vote=37.5,
            source="sos",
            reported_at=datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc),
        )
    )
    results = db.election_results.list_by_race("TX-2026")
    assert len(results) == 1
    assert results[0].votes == 12_345
