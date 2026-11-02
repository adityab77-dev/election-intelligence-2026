"""Repository layer over the Phase 2 entities.

A small generic :class:`BaseRepository` implements CRUD (insert, upsert, get,
list, find, delete, count) against DuckDB, mapping Pydantic row models to and
from parameterised SQL. Concrete repositories bind a model, table and primary
key, and add a few convenience finders.

Table and column names come only from this module (never user input), so the
f-string interpolation used to build statements is not an injection vector;
all *values* are passed as bound parameters.

No forecasting logic lives here.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel

from election_intelligence.data.storage.entities import (
    Candidate,
    ElectionResult,
    Poll,
    PollAggregate,
    SenateRace,
    SimulationResult,
    SimulationRun,
    State,
    StateForecast,
)

if TYPE_CHECKING:
    from election_intelligence.data.storage.duckdb_client import DuckDBClient

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository for a single table."""

    #: Subclasses set these.
    model: type[ModelT]
    table: str
    pk: str
    #: Fields stored as JSON text and (de)serialised transparently.
    json_fields: frozenset[str] = frozenset()

    def __init__(self, client: DuckDBClient) -> None:
        self._client = client

    # -- mapping helpers ------------------------------------------------------
    @property
    def columns(self) -> list[str]:
        return list(self.model.model_fields.keys())

    def _to_row(self, entity: ModelT) -> list[Any]:
        row: list[Any] = []
        for name in self.columns:
            value = getattr(entity, name)
            if isinstance(value, Enum):
                value = value.value
            elif name in self.json_fields and value is not None:
                value = json.dumps(value)
            row.append(value)
        return row

    def _from_row(self, data: dict[str, Any]) -> ModelT:
        parsed = dict(data)
        for name in self.json_fields:
            raw = parsed.get(name)
            if isinstance(raw, str):
                parsed[name] = json.loads(raw)
        return self.model.model_validate(parsed)

    # -- write ----------------------------------------------------------------
    def insert(self, entity: ModelT) -> ModelT:
        cols = self.columns
        placeholders = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({placeholders})"
        self._client.run(sql, self._to_row(entity))
        return entity

    def upsert(self, entity: ModelT) -> ModelT:
        cols = self.columns
        placeholders = ", ".join(["?"] * len(cols))
        updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != self.pk)
        conflict = (
            f"DO UPDATE SET {updates}" if updates else "DO NOTHING"
        )
        sql = (
            f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({self.pk}) {conflict}"
        )
        self._client.run(sql, self._to_row(entity))
        return entity

    def delete(self, pk_value: Any) -> bool:
        existed = self.get(pk_value) is not None
        self._client.run(f"DELETE FROM {self.table} WHERE {self.pk} = ?", [pk_value])
        return existed

    # -- read -----------------------------------------------------------------
    def get(self, pk_value: Any) -> ModelT | None:
        row = self._client.fetch_one(
            f"SELECT * FROM {self.table} WHERE {self.pk} = ?", [pk_value]
        )
        return self._from_row(row) if row is not None else None

    def find(self, where: str, parameters: list[Any]) -> list[ModelT]:
        rows = self._client.fetch_all(
            f"SELECT * FROM {self.table} WHERE {where}", parameters
        )
        return [self._from_row(r) for r in rows]

    def list(
        self, *, limit: int | None = None, order_by: str | None = None
    ) -> list[ModelT]:
        sql = f"SELECT * FROM {self.table}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        return [self._from_row(r) for r in self._client.fetch_all(sql)]

    def count(self) -> int:
        row = self._client.fetch_one(f"SELECT COUNT(*) AS n FROM {self.table}")
        return int(row["n"]) if row else 0


# --- Concrete repositories ---------------------------------------------------
class StateRepository(BaseRepository[State]):
    model = State
    table = "states"
    pk = "state_code"


class SenateRaceRepository(BaseRepository[SenateRace]):
    model = SenateRace
    table = "senate_races"
    pk = "race_id"

    def list_by_state(self, state_code: str) -> list[SenateRace]:
        return self.find("state_code = ?", [state_code])


class CandidateRepository(BaseRepository[Candidate]):
    model = Candidate
    table = "candidates"
    pk = "candidate_id"

    def list_by_race(self, race_id: str) -> list[Candidate]:
        return self.find("race_id = ?", [race_id])


class PollRepository(BaseRepository[Poll]):
    model = Poll
    table = "polls"
    pk = "poll_id"

    def list_by_race(self, race_id: str) -> list[Poll]:
        return self.find("race_id = ?", [race_id])


class PollAggregateRepository(BaseRepository[PollAggregate]):
    model = PollAggregate
    table = "poll_aggregates"
    pk = "aggregate_id"

    def list_by_race(self, race_id: str) -> list[PollAggregate]:
        return self.find("race_id = ?", [race_id])

    def latest_for_race(self, race_id: str) -> PollAggregate | None:
        row = self._client.fetch_one(
            f"SELECT * FROM {self.table} WHERE race_id = ? "
            "ORDER BY as_of DESC, created_at DESC LIMIT 1",
            [race_id],
        )
        return self._from_row(row) if row is not None else None


class StateForecastRepository(BaseRepository[StateForecast]):
    model = StateForecast
    table = "state_forecasts"
    pk = "forecast_id"

    def list_by_race(self, race_id: str) -> list[StateForecast]:
        return self.find("race_id = ?", [race_id])

    def latest_for_race(self, race_id: str) -> StateForecast | None:
        row = self._client.fetch_one(
            f"SELECT * FROM {self.table} WHERE race_id = ? "
            "ORDER BY forecast_date DESC, created_at DESC LIMIT 1",
            [race_id],
        )
        return self._from_row(row) if row is not None else None


class SimulationRunRepository(BaseRepository[SimulationRun]):
    model = SimulationRun
    table = "simulation_runs"
    pk = "run_id"

    def latest(self) -> SimulationRun | None:
        row = self._client.fetch_one(
            f"SELECT * FROM {self.table} ORDER BY created_at DESC LIMIT 1"
        )
        return self._from_row(row) if row is not None else None


class SimulationResultRepository(BaseRepository[SimulationResult]):
    model = SimulationResult
    table = "simulation_results"
    pk = "run_id"
    json_fields = frozenset(
        {"seat_histogram", "paths", "conditionals", "influential_states"}
    )


class ElectionResultRepository(BaseRepository[ElectionResult]):
    model = ElectionResult
    table = "election_results"
    pk = "result_id"

    def list_by_race(self, race_id: str) -> list[ElectionResult]:
        return self.find("race_id = ?", [race_id])


__all__ = [
    "BaseRepository",
    "StateRepository",
    "SenateRaceRepository",
    "CandidateRepository",
    "PollRepository",
    "PollAggregateRepository",
    "StateForecastRepository",
    "SimulationRunRepository",
    "SimulationResultRepository",
    "ElectionResultRepository",
]
