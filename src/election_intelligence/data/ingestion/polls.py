"""Minimal Senate polling ingestion (Phase 3, MVP-scoped).

Deliberately narrow: ingests polls for the eight MVP Senate battleground states
only, validates them, and stores them via the Phase 2 ``PollRepository``. This
is **not** a generalised ingestion framework.

It contains **no forecasting logic**: :func:`simple_polling_average` is a plain
descriptive mean of recent polls, provided so the MVP can be smoke-tested
(``Georgia -> latest polling average``). The weighted aggregation engine
(pollster quality, house effects, recency decay) is Phase 4.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError as PydanticValidationError

from election_intelligence.data.storage.entities import Poll
from election_intelligence.exceptions import IngestionError
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from election_intelligence.data.storage.database import Database

logger = get_logger(__name__)

ELECTION_DATE = date(2026, 11, 3)
MARGIN_LIMIT = 100.0

# MVP battleground states -> their 2026 Senate race id (see storage seeds).
BATTLEGROUND_RACES: dict[str, str] = {
    "GA": "GA-2026",
    "NC": "NC-2026",
    "ME": "ME-2026",
    "MI": "MI-2026",
    "NH": "NH-2026",
    "TX": "TX-2026",
    "OH": "OH-2026-S",
    "IA": "IA-2026",
}
BATTLEGROUND_RACE_IDS: frozenset[str] = frozenset(BATTLEGROUND_RACES.values())

SAMPLE_POLLS_PATH = Path(__file__).resolve().parent / "sample_polls.json"


# --- Validation --------------------------------------------------------------
def validate_poll(
    poll: Poll,
    *,
    allowed_races: frozenset[str] | None = BATTLEGROUND_RACE_IDS,
    election_date: date = ELECTION_DATE,
) -> list[str]:
    """Return a list of semantic validation errors (empty means valid).

    Type/shape validation is already handled by the :class:`Poll` model; this
    layer adds the MVP-specific semantic checks.
    """
    errors: list[str] = []
    if allowed_races is not None and poll.race_id not in allowed_races:
        errors.append(f"race_id {poll.race_id!r} not in the MVP battleground set")
    if poll.field_start is not None and poll.field_start > poll.field_end:
        errors.append("field_start is after field_end")
    if poll.field_end > election_date:
        errors.append(f"field_end {poll.field_end} is after election day {election_date}")
    if poll.sample_size is not None and poll.sample_size <= 0:
        errors.append("sample_size must be positive")
    if not -MARGIN_LIMIT <= poll.margin_dem_minus_rep <= MARGIN_LIMIT:
        errors.append("margin_dem_minus_rep is out of the plausible range")
    return errors


def _deterministic_poll_id(poll: Poll) -> str:
    """Stable id from a poll's natural key, so re-ingesting is idempotent."""
    population = poll.population.value if poll.population is not None else "NA"
    key = f"{poll.race_id}|{poll.pollster}|{poll.field_end.isoformat()}|{population}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def deterministic_poll_id(poll: Poll) -> str:
    """Public: stable natural-key id for a poll (used by source adapters to dedup)."""
    return _deterministic_poll_id(poll)


# --- Reports / results -------------------------------------------------------
@dataclass
class IngestionReport:
    """Outcome of an ingestion run."""

    ingested: int = 0
    rejected: int = 0
    errors: list[tuple[str, list[str]]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.ingested + self.rejected


@dataclass
class PollingAverage:
    """A plain descriptive polling average (not a forecast)."""

    race_id: str
    mean_margin_dem_minus_rep: float
    n_polls: int
    latest_field_end: date
    window_days: int | None


# --- Ingestor ----------------------------------------------------------------
class PollIngestor:
    """Validates and stores polls for the MVP battleground races."""

    def __init__(
        self,
        database: Database,
        *,
        allowed_races: frozenset[str] | None = BATTLEGROUND_RACE_IDS,
    ) -> None:
        self._db = database
        self._allowed = allowed_races

    def ingest(self, polls: Iterable[Poll]) -> IngestionReport:
        """Validate and upsert already-parsed polls."""
        report = IngestionReport()
        for poll in polls:
            errors = validate_poll(poll, allowed_races=self._allowed)
            if errors:
                report.rejected += 1
                report.errors.append((poll.poll_id, errors))
                logger.warning("rejected poll %s: %s", poll.poll_id, "; ".join(errors))
                continue
            self._db.polls.upsert(poll)
            report.ingested += 1
        return report

    def ingest_records(self, records: Iterable[Mapping[str, Any]]) -> IngestionReport:
        """Parse raw dict records into polls, then validate and store them."""
        report = IngestionReport()
        parsed: list[Poll] = []
        for index, record in enumerate(records):
            try:
                poll = Poll.model_validate(record)
            except PydanticValidationError as exc:
                report.rejected += 1
                report.errors.append((f"record[{index}]", [str(exc)]))
                logger.warning("rejected record[%d]: malformed", index)
                continue
            if not record.get("poll_id"):
                poll.poll_id = _deterministic_poll_id(poll)
            parsed.append(poll)

        stored = self.ingest(parsed)
        report.ingested += stored.ingested
        report.rejected += stored.rejected
        report.errors.extend(stored.errors)
        return report

    def ingest_file(self, path: str | Path | None = None) -> IngestionReport:
        """Ingest polls from a JSON array file (defaults to the bundled sample)."""
        path = Path(path) if path is not None else SAMPLE_POLLS_PATH
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IngestionError(f"cannot read polls file: {path}") from exc
        if not isinstance(data, list):
            raise IngestionError("polls file must contain a JSON array")
        return self.ingest_records(data)


# --- Descriptive queries (NOT forecasting) -----------------------------------
def latest_poll(database: Database, race_id: str) -> Poll | None:
    """The single most recent poll for a race (by field_end), or ``None``."""
    polls = database.polls.list_by_race(race_id)
    if not polls:
        return None
    return max(polls, key=lambda p: p.field_end)


def simple_polling_average(
    database: Database, race_id: str, *, window_days: int | None = 21
) -> PollingAverage | None:
    """Unweighted mean margin of recent polls for a race, or ``None``.

    With ``window_days`` set, only polls whose ``field_end`` is within that many
    days of the most recent poll are included. This is a descriptive helper for
    the MVP, deliberately with no pollster weighting, house-effect removal, or
    recency decay (those belong to the Phase 4 aggregation engine).
    """
    polls = database.polls.list_by_race(race_id)
    if not polls:
        return None
    latest = max(p.field_end for p in polls)
    selected = polls
    if window_days is not None:
        cutoff = latest - timedelta(days=window_days)
        selected = [p for p in polls if p.field_end >= cutoff]
    mean = sum(p.margin_dem_minus_rep for p in selected) / len(selected)
    return PollingAverage(
        race_id=race_id,
        mean_margin_dem_minus_rep=mean,
        n_polls=len(selected),
        latest_field_end=latest,
        window_days=window_days,
    )


__all__ = [
    "BATTLEGROUND_RACES",
    "BATTLEGROUND_RACE_IDS",
    "SAMPLE_POLLS_PATH",
    "IngestionReport",
    "PollingAverage",
    "PollIngestor",
    "validate_poll",
    "latest_poll",
    "simple_polling_average",
]
