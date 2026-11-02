"""Seed-data framework.

Loads reference data from JSON files into the database via the repository layer.
Each file ``seeds/<entity>.json`` holds a list of row objects. Loading is
idempotent (upsert by primary key) and ordered so foreign-key parents load
before their children.

Seed files are small, non-sensitive reference data and are committed; bulk
downloaded data is never seeded this way (it belongs under the gitignored
``data/`` tree). See ``REFERENCE_DATA_CHECKLIST.md`` for provenance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from election_intelligence.data.storage.entities import (
    Candidate,
    Poll,
    SenateRace,
    State,
)
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from election_intelligence.data.storage.database import Database
    from election_intelligence.data.storage.repositories import BaseRepository

logger = get_logger(__name__)

DEFAULT_SEEDS_DIR = Path(__file__).resolve().parent / "seeds"

# FK-safe load order: parents before children.
SEED_ORDER: tuple[str, ...] = ("states", "senate_races", "candidates", "polls")


class SeedLoader:
    """Loads seed JSON files into the database, idempotently."""

    def __init__(self, database: Database, seeds_dir: Path | None = None) -> None:
        self._db = database
        self._dir = seeds_dir or DEFAULT_SEEDS_DIR

    def _target(self, name: str) -> tuple[BaseRepository, type[BaseModel]]:
        mapping: dict[str, tuple[BaseRepository, type[BaseModel]]] = {
            "states": (self._db.states, State),
            "senate_races": (self._db.senate_races, SenateRace),
            "candidates": (self._db.candidates, Candidate),
            "polls": (self._db.polls, Poll),
        }
        if name not in mapping:
            raise KeyError(f"no seed target registered for '{name}'")
        return mapping[name]

    def load_file(self, name: str, path: Path | None = None) -> int:
        """Load one seed file; returns the number of rows upserted."""
        path = path or (self._dir / f"{name}.json")
        repo, model = self._target(name)
        rows = json.loads(path.read_text(encoding="utf-8"))
        for item in rows:
            repo.upsert(model.model_validate(item))
        logger.info("seeded %d row(s) into %s", len(rows), name)
        return len(rows)

    def load_all(self) -> dict[str, int]:
        """Load every present seed file in FK-safe order."""
        summary: dict[str, int] = {}
        for name in SEED_ORDER:
            path = self._dir / f"{name}.json"
            if path.exists():
                summary[name] = self.load_file(name, path)
        return summary


__all__ = ["SeedLoader", "DEFAULT_SEEDS_DIR", "SEED_ORDER"]
