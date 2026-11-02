"""Database facade.

Bundles a :class:`DuckDBClient`, the :class:`Migrator`, and one repository per
entity behind a single object, and exposes convenience operations
(``initialize``, ``migrate``, ``table_names``, ``table_counts``). This is the
primary entry point for the storage layer.

    from election_intelligence.data.storage import Database

    with Database() as db:
        db.initialize(seed=True)
        print(db.table_counts())
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

from election_intelligence.data.storage.duckdb_client import DuckDBClient
from election_intelligence.data.storage.migrations import Migrator
from election_intelligence.data.storage.repositories import (
    CandidateRepository,
    ElectionResultRepository,
    PollAggregateRepository,
    PollRepository,
    SenateRaceRepository,
    SimulationResultRepository,
    SimulationRunRepository,
    StateForecastRepository,
    StateRepository,
)
from election_intelligence.data.storage.seed import SeedLoader


class Database:
    """One object tying together the client, migrations, and repositories."""

    def __init__(
        self, path: Path | str | None = None, *, read_only: bool = False
    ) -> None:
        self.client = DuckDBClient(path, read_only=read_only)
        self.migrator = Migrator(self.client)

        self.states = StateRepository(self.client)
        self.senate_races = SenateRaceRepository(self.client)
        self.candidates = CandidateRepository(self.client)
        self.polls = PollRepository(self.client)
        self.poll_aggregates = PollAggregateRepository(self.client)
        self.state_forecasts = StateForecastRepository(self.client)
        self.simulation_runs = SimulationRunRepository(self.client)
        self.simulation_results = SimulationResultRepository(self.client)
        self.election_results = ElectionResultRepository(self.client)

    @property
    def path(self) -> Path:
        return self.client.path

    def migrate(self) -> list[int]:
        """Apply pending migrations; return versions applied now."""
        return self.migrator.apply_all()

    def initialize(self, *, seed: bool = False) -> list[int]:
        """Create the schema (and optionally load seed data)."""
        applied = self.migrate()
        if seed:
            SeedLoader(self).load_all()
        return applied

    def table_names(self) -> set[str]:
        rows = self.client.fetch_all(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        )
        return {str(r["table_name"]) for r in rows}

    def table_counts(self) -> dict[str, int]:
        """Row counts for each entity table (for diagnostics / init summary)."""
        repos = {
            "states": self.states,
            "senate_races": self.senate_races,
            "candidates": self.candidates,
            "polls": self.polls,
            "poll_aggregates": self.poll_aggregates,
            "state_forecasts": self.state_forecasts,
            "simulation_runs": self.simulation_runs,
            "simulation_results": self.simulation_results,
            "election_results": self.election_results,
        }
        return {name: repo.count() for name, repo in repos.items()}

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> Database:
        self.client.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


__all__ = ["Database"]
