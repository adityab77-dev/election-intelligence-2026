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


__all__ = ["ResultsIngestor", "ResultsReport"]
