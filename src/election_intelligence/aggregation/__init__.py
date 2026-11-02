"""Poll aggregation (Phase 4).

Computes weighted, per-state poll aggregates (sample-size x recency x quality)
with a variance estimate and a contributing-poll breakdown. Kept separate from
the Phase 5 forecast engine: this produces aggregates, not forecasts.
"""

from __future__ import annotations

from election_intelligence.aggregation.engine import (
    AggregateResult,
    AggregationConfig,
    PollAggregator,
    PollContribution,
)

__all__ = [
    "AggregateResult",
    "AggregationConfig",
    "PollAggregator",
    "PollContribution",
]
