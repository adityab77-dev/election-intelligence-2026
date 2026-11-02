"""Integration tests for the repository layer (CRUD, FK integrity, JSON)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timezone

import pytest

pytest.importorskip("duckdb")

from election_intelligence.data.storage import Database  # noqa: E402
from election_intelligence.data.storage.entities import (  # noqa: E402
    Candidate,
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
def test_state_forecast_json_roundtrip(db: Database) -> None:
    _seed_race(db)
    run = SimulationRun(
        regime="pre_election", n_simulations=50_000, random_seed=42, inputs_hash="h1"
    )
    db.simulation_runs.insert(run)

    drivers = {"polls": 1.2, "fundamentals": -0.4}
    db.state_forecasts.insert(
        StateForecast(
            run_id=run.run_id,
            race_id="TX-2026",
            mean_margin=-1.5,
            std_margin=5.0,
            drivers=drivers,
        )
    )
    stored = db.state_forecasts.list_by_run(run.run_id)
    assert len(stored) == 1
    assert stored[0].drivers == drivers


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
