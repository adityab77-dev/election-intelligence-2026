"""Ingestion: load and normalise external data sources.

Phase 3 provides a minimal, battleground-scoped polling pipeline (``polls``).
The abstract :class:`DataSource` contract remains for future sources.
"""

from __future__ import annotations

from election_intelligence.data.ingestion.base import DataSource
from election_intelligence.data.ingestion.polls import (
    BATTLEGROUND_RACE_IDS,
    BATTLEGROUND_RACES,
    IngestionReport,
    PollingAverage,
    PollIngestor,
    latest_poll,
    simple_polling_average,
    validate_poll,
)

__all__ = [
    "DataSource",
    "BATTLEGROUND_RACES",
    "BATTLEGROUND_RACE_IDS",
    "IngestionReport",
    "PollingAverage",
    "PollIngestor",
    "latest_poll",
    "simple_polling_average",
    "validate_poll",
]
