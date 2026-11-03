"""Pluggable poll sources (Phase A).

A :class:`PollSource` fetches real polls from an external source and returns
``Poll`` entities for the existing ``PollIngestor`` to validate and store. The
interface is source-agnostic so a future DDHQ adapter can replace Wikipedia
without changes downstream of the ``polls`` table.
"""

from __future__ import annotations

from election_intelligence.data.ingestion.sources.base import PollSource
from election_intelligence.data.ingestion.sources.wikipedia import WikipediaPollSource

__all__ = ["PollSource", "WikipediaPollSource"]
