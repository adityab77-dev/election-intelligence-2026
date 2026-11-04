"""Results ingestor: validate and store ``RaceResults`` (Phase E)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from election_intelligence.data.ingestion.results.base import RaceResults
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from election_intelligence.data.ingestion.results.base import ResultsSource
    from election_intelligence.data.storage.database import Database

logger = get_logger(__name__)


@dataclass
class ResultsReport:
    snapshots: int = 0
    results: int = 0
    skipped: int = 0


class ResultsIngestor:
    """Validates and stores results snapshots + candidate rows (append-only)."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def ingest(self, race_results: Iterable[RaceResults]) -> ResultsReport:
        report = ResultsReport()
        for item in race_results:
            snapshot = item.snapshot
            if not (0.0 <= snapshot.percent_reporting <= 110.0) or snapshot.total_votes < 0:
                report.skipped += 1
                logger.warning("rejected snapshot for %s (bad values)", snapshot.race_id)
                continue
            self._db.reporting_snapshots.upsert(snapshot)
            report.snapshots += 1
            for candidate in item.candidates:
                self._db.election_results.insert(candidate)
                report.results += 1
        return report

    def ingest_source(self, source: ResultsSource) -> ResultsReport:
        return self.ingest(source.fetch())


def ingest_all_results(database: Database) -> ResultsReport:
    """Ingest results using Clarity as primary and Wikipedia as fallback.

    Clarity (official state JSON) is authoritative for its configured states;
    Wikipedia covers every other battleground. A combined report is returned.
    """
    from election_intelligence.data.ingestion.results.clarity import (
        CLARITY_RACE_IDS,
        ClarityResultsSource,
    )
    from election_intelligence.data.ingestion.results.wikipedia import (
        WikipediaResultsSource,
    )
    from election_intelligence.data.ingestion.sources.wikipedia import WIKIPEDIA_RACES

    ingestor = ResultsIngestor(database)
    clarity = ClarityResultsSource().fetch()
    wiki_races = tuple(r for r in WIKIPEDIA_RACES if r.race_id not in CLARITY_RACE_IDS)
    wikipedia = WikipediaResultsSource(races=wiki_races).fetch()
    return ingestor.ingest(clarity + wikipedia)


__all__ = ["ResultsIngestor", "ResultsReport", "ingest_all_results"]
