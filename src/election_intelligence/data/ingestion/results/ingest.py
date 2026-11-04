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
            # Hardening: reject a snapshot whose total drops below the last good
            # one (a transient feed glitch), unless the race has been called.
            previous = self._db.reporting_snapshots.latest_for_race(snapshot.race_id)
            if (
                previous is not None
                and snapshot.total_votes < previous.total_votes
                and not snapshot.is_called
            ):
                report.skipped += 1
                logger.warning(
                    "rejected %s: total votes decreased %d -> %d",
                    snapshot.race_id, previous.total_votes, snapshot.total_votes,
                )
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
    """Ingest results from official sources first, Wikipedia as fallback.

    Official feeds (Clarity for Iowa, Georgia SoS) are authoritative for their
    states; Wikipedia covers every other battleground. Combined report returned.
    """
    from election_intelligence.data.ingestion.results.clarity import (
        CLARITY_RACE_IDS,
        ClarityResultsSource,
    )
    from election_intelligence.data.ingestion.results.georgia import (
        GEORGIA_RACE_IDS,
        GeorgiaResultsSource,
    )
    from election_intelligence.data.ingestion.results.wikipedia import (
        WikipediaResultsSource,
    )
    from election_intelligence.data.ingestion.sources.wikipedia import WIKIPEDIA_RACES

    official = CLARITY_RACE_IDS | GEORGIA_RACE_IDS
    ingestor = ResultsIngestor(database)
    results = ClarityResultsSource().fetch() + GeorgiaResultsSource().fetch()
    wiki_races = tuple(r for r in WIKIPEDIA_RACES if r.race_id not in official)
    results += WikipediaResultsSource(races=wiki_races).fetch()
    return ingestor.ingest(results)


__all__ = ["ResultsIngestor", "ResultsReport", "ingest_all_results"]
