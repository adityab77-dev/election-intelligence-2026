"""Typed domain models for the Phase 2 storage entities.

One Pydantic model per table (the "row" type), plus the storage-layer enums.
These give the repository layer strong typing and validation at the boundary.
They carry no behaviour and no forecasting logic — just shape and defaults.

Application-generated primary keys (poll/aggregate/forecast/result ids and run
ids) default to a UUID so callers need not supply them; natural keys
(``state_code``, ``race_id``, ``candidate_id``) are always supplied by the caller.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Timezone-aware current UTC timestamp (stored in TIMESTAMPTZ columns)."""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    """Opaque application-generated primary key."""
    return str(uuid4())


# --- Enums (mirror the SQL ENUM types in 0001_initial_schema.sql) ------------
class Party(str, Enum):
    DEM = "DEM"
    REP = "REP"
    IND = "IND"
    LIB = "LIB"
    GRN = "GRN"
    OTH = "OTH"


class CountingRule(str, Enum):
    PLURALITY = "plurality"
    MAJORITY_RUNOFF = "majority_runoff"
    RANKED_CHOICE = "ranked_choice"


class PollPopulation(str, Enum):
    LIKELY_VOTER = "LV"
    REGISTERED_VOTER = "RV"
    ADULT = "A"
    VOTER = "V"


class SimRegime(str, Enum):
    PRE_ELECTION = "pre_election"
    LIVE = "live"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# --- Row models --------------------------------------------------------------
class State(BaseModel):
    state_code: str
    name: str
    time_zone: str
    poll_close_utc: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class SenateRace(BaseModel):
    race_id: str
    state_code: str
    seat_class: str | None = None
    is_special: bool = False
    office: str = "US Senate"
    counting_rule: CountingRule = CountingRule.PLURALITY
    incumbent_party: Party | None = None
    expert_rating: str | None = None
    recount_margin_pct: float | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Candidate(BaseModel):
    candidate_id: str
    race_id: str
    name: str
    party: Party
    is_incumbent: bool = False
    caucuses_with: Party | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Poll(BaseModel):
    poll_id: str = Field(default_factory=_new_id)
    race_id: str
    pollster: str
    pollster_grade: str | None = None
    field_start: date | None = None
    field_end: date
    sample_size: int | None = None
    population: PollPopulation | None = None
    mode: str | None = None
    sponsor: str | None = None
    margin_dem_minus_rep: float
    house_effect_adj: float | None = None
    url: str | None = None
    ingested_at: datetime = Field(default_factory=_utcnow)


class PollAggregate(BaseModel):
    aggregate_id: str = Field(default_factory=_new_id)
    race_id: str
    as_of: date
    mean_margin: float
    std_error: float | None = None
    n_polls: int = 0
    effective_sample_size: float | None = None
    method: str = "v1"
    created_at: datetime = Field(default_factory=_utcnow)


class SimulationRun(BaseModel):
    run_id: str = Field(default_factory=_new_id)
    regime: SimRegime
    n_simulations: int
    random_seed: int
    inputs_hash: str
    code_version: str | None = None
    trigger: str | None = None
    status: RunStatus = RunStatus.PENDING
    notes: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class StateForecast(BaseModel):
    """Per-state pre-election forecast distribution (Phase 5).

    A margin is modelled as Normal(mean_margin, sigma). This is the input the
    Phase 6 Monte Carlo will consume; it carries no win probabilities itself.
    """

    forecast_id: str = Field(default_factory=_new_id)
    race_id: str
    state_code: str | None = None
    mean_margin: float
    sigma: float
    confidence_level: ConfidenceLevel
    poll_count: int = 0
    forecast_date: date
    method: str = "poll_only_v1"
    inputs_hash: str
    created_at: datetime = Field(default_factory=_utcnow)


class SimulationResult(BaseModel):
    run_id: str
    prob_rep_control: float
    prob_dem_control: float
    prob_undetermined: float = 0.0
    mc_std_error: float | None = None
    rep_seats_median: int | None = None
    rep_seats_p10: int | None = None
    rep_seats_p90: int | None = None
    seat_histogram: dict[str, Any] | None = None
    paths: list[Any] | None = None
    conditionals: dict[str, Any] | None = None
    expected_rep_seats: float | None = None
    expected_dem_seats: float | None = None
    convergence_delta: float | None = None
    influential_states: list[Any] | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class ElectionResult(BaseModel):
    result_id: str = Field(default_factory=_new_id)
    race_id: str
    candidate_id: str
    votes: int = 0
    pct_expected_vote: float | None = None
    is_called: bool = False
    source: str
    reported_at: datetime
    quarantined: bool = False
    quarantine_reason: str | None = None
    ingested_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "Party",
    "CountingRule",
    "PollPopulation",
    "SimRegime",
    "RunStatus",
    "ConfidenceLevel",
    "State",
    "SenateRace",
    "Candidate",
    "Poll",
    "PollAggregate",
    "SimulationRun",
    "StateForecast",
    "SimulationResult",
    "ElectionResult",
]
