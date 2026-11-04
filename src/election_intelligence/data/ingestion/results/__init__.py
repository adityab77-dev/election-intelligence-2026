"""Election-results ingestion (Phase E).

A pluggable `ResultsSource` (Wikipedia now; DDHQ/SoS later) → `ResultsIngestor`
→ `election_results` + `reporting_snapshots`. Feeds the live blend engine.
"""

from __future__ import annotations

from election_intelligence.data.ingestion.results.base import RaceResults, ResultsSource
from election_intelligence.data.ingestion.results.clarity import (
    CLARITY_RACES,
    CLARITY_RACE_IDS,
    ClarityResultsSource,
)
from election_intelligence.data.ingestion.results.georgia import (
    GEORGIA_RACE_IDS,
    GeorgiaResultsSource,
)
from election_intelligence.data.ingestion.results.ingest import (
    ResultsIngestor,
    ResultsReport,
    ingest_all_results,
)
from election_intelligence.data.ingestion.results.wikipedia import WikipediaResultsSource

__all__ = [
    "ResultsSource",
    "RaceResults",
    "ResultsIngestor",
    "ResultsReport",
    "ingest_all_results",
    "WikipediaResultsSource",
    "ClarityResultsSource",
    "CLARITY_RACES",
    "CLARITY_RACE_IDS",
    "GeorgiaResultsSource",
    "GEORGIA_RACE_IDS",
]
