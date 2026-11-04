"""Election-results ingestion (Phase E).

A pluggable `ResultsSource` (Wikipedia now; DDHQ/SoS later) → `ResultsIngestor`
→ `election_results` + `reporting_snapshots`. Feeds the live blend engine.
"""

from __future__ import annotations

from election_intelligence.data.ingestion.results.base import RaceResults, ResultsSource
from election_intelligence.data.ingestion.results.ingest import (
    ResultsIngestor,
    ResultsReport,
)
from election_intelligence.data.ingestion.results.wikipedia import WikipediaResultsSource

__all__ = [
    "ResultsSource",
    "RaceResults",
    "ResultsIngestor",
    "ResultsReport",
    "WikipediaResultsSource",
]
