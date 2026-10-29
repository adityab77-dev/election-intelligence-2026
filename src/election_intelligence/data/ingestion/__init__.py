"""Ingestion: load and normalise external data sources.

Concrete source readers (polls, historical results, demographics, …) will
implement the :class:`~election_intelligence.data.ingestion.base.DataSource`
interface defined here.
"""

from __future__ import annotations

from election_intelligence.data.ingestion.base import DataSource

__all__ = ["DataSource"]
