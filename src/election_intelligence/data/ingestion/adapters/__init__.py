"""Source adapters: one module per external data source.

Each adapter implements the :class:`~election_intelligence.data.ingestion.base.DataSource`
contract (results feed, polls, fundamentals, markets, news). Implemented from
Phase 3 (loaders) and Phase 9 (live results). No adapters exist yet.
"""

from __future__ import annotations

__all__: list[str] = []
