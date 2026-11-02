"""Unit tests for the storage entity models (no database required)."""

from __future__ import annotations

import pytest

from election_intelligence.data.storage.entities import (
    Candidate,
    CountingRule,
    Party,
    SenateRace,
    SimulationRun,
    State,
)


@pytest.mark.unit
def test_state_requires_core_fields() -> None:
    state = State(state_code="TX", name="Texas", time_zone="America/Chicago")
    assert state.poll_close_utc is None
    assert state.created_at is not None  # default_factory applied


@pytest.mark.unit
def test_race_defaults() -> None:
    race = SenateRace(race_id="TX-2026", state_code="TX")
    assert race.counting_rule is CountingRule.PLURALITY
    assert race.is_special is False
    assert race.office == "US Senate"


@pytest.mark.unit
def test_enum_coercion_from_string() -> None:
    candidate = Candidate(
        candidate_id="c1", race_id="TX-2026", name="A. Candidate", party="REP"
    )
    assert candidate.party is Party.REP


@pytest.mark.unit
def test_simulation_run_autogenerates_id() -> None:
    run = SimulationRun(
        regime="pre_election", n_simulations=100_000, random_seed=7, inputs_hash="abc"
    )
    assert run.run_id  # UUID default
    assert run.status.value == "pending"
