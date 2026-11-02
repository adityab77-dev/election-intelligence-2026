"""Weighted poll aggregation engine (Phase 4).

Turns the poll records stored in DuckDB into a per-state weighted aggregate:

    AggregateResult(state, margin, variance, poll_count, last_updated, ...)

The weighted margin combines three weights (sample size x recency x quality).
The variance estimate combines the sampling error of the weighted mean with the
weighted dispersion between polls, so it is well-defined even for a single poll.

This is the input the forecast engine (Phase 5) will consume. It deliberately
stops short of a forecast: no fundamentals prior, no margin distribution, no
simulation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from election_intelligence.aggregation.weights import (
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_QUALITY,
    DEFAULT_SAMPLE_SIZE,
    MAX_EFFECTIVE_N,
    quality_weight,
    recency_weight,
    sample_size_weight,
)
from election_intelligence.data.storage.entities import Poll, PollAggregate
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from election_intelligence.data.storage.database import Database

logger = get_logger(__name__)

# Margin standard error (points) for a single poll is approximated as
# SAMPLING_CONSTANT / sqrt(n); ~100 gives ~3.5 pts at n=800, matching reality.
SAMPLING_CONSTANT = 100.0


@dataclass(frozen=True)
class AggregationConfig:
    """Tunable parameters for the weighting and variance estimate."""

    half_life_days: float = DEFAULT_HALF_LIFE_DAYS
    max_effective_n: int = MAX_EFFECTIVE_N
    default_sample_size: int = DEFAULT_SAMPLE_SIZE
    default_quality: float = DEFAULT_QUALITY
    sampling_constant: float = SAMPLING_CONSTANT
    method: str = "weighted_v1"


@dataclass(frozen=True)
class PollContribution:
    """One poll's contribution to an aggregate (diagnostic breakdown)."""

    poll_id: str
    pollster: str
    field_end: date
    margin: float
    sample_size: int | None
    age_days: int
    weight_sample: float
    weight_recency: float
    weight_quality: float
    weight: float
    weight_share: float


@dataclass(frozen=True)
class AggregateResult:
    """A weighted poll aggregate for one race, with its poll breakdown."""

    race_id: str
    state_code: str | None
    margin: float
    variance: float
    std_error: float
    poll_count: int
    effective_sample_size: float
    last_updated: date
    reference_date: date
    method: str
    contributions: list[PollContribution]

    def to_entity(self) -> PollAggregate:
        """Map to the persistable storage entity (deterministic id)."""
        return PollAggregate(
            aggregate_id=f"{self.race_id}:{self.last_updated.isoformat()}:{self.method}",
            race_id=self.race_id,
            as_of=self.last_updated,
            mean_margin=self.margin,
            std_error=self.std_error,
            n_polls=self.poll_count,
            effective_sample_size=self.effective_sample_size,
            method=self.method,
        )


class PollAggregator:
    """Computes weighted poll aggregates from stored polls."""

    def __init__(self, config: AggregationConfig | None = None) -> None:
        self._cfg = config or AggregationConfig()

    @property
    def config(self) -> AggregationConfig:
        return self._cfg

    def aggregate(
        self,
        polls: list[Poll],
        *,
        race_id: str,
        state_code: str | None = None,
        reference_date: date | None = None,
    ) -> AggregateResult | None:
        """Aggregate a list of polls for one race; ``None`` if empty."""
        if not polls:
            return None

        cfg = self._cfg
        last_updated = max(p.field_end for p in polls)
        reference = reference_date or last_updated

        # Per-poll weights and components.
        weighted: list[tuple[Poll, float, float, float, float, int]] = []
        for poll in polls:
            w_sample = sample_size_weight(
                poll.sample_size,
                max_effective_n=cfg.max_effective_n,
                default_sample_size=cfg.default_sample_size,
            )
            age = (reference - poll.field_end).days
            w_recency = recency_weight(age, half_life_days=cfg.half_life_days)
            w_quality = quality_weight(poll.pollster_grade, default=cfg.default_quality)
            weight = w_sample * w_recency * w_quality
            weighted.append((poll, w_sample, w_recency, w_quality, weight, age))

        sum_w = sum(item[4] for item in weighted)
        if sum_w <= 0:  # pragma: no cover - weights are strictly positive
            weighted = [(p, ws, wr, wq, 1.0, age) for (p, ws, wr, wq, _, age) in weighted]
            sum_w = float(len(weighted))

        margin = sum(item[0].margin_dem_minus_rep * item[4] for item in weighted) / sum_w

        # Kish effective sample size of the weights.
        sum_w2 = sum(item[4] ** 2 for item in weighted)
        n_eff = (sum_w**2) / sum_w2 if sum_w2 > 0 else float(len(weighted))

        # Between-poll dispersion, as variance of the weighted mean.
        dispersion = (
            sum(item[4] * (item[0].margin_dem_minus_rep - margin) ** 2 for item in weighted)
            / sum_w
        )
        if n_eff > 1:
            dispersion *= n_eff / (n_eff - 1)  # small-sample (unbiased) correction
        var_dispersion_mean = dispersion / n_eff

        # Sampling variance of the weighted mean: sum (share_i^2 * s_i^2).
        var_sampling_mean = 0.0
        for poll, _ws, _wr, _wq, weight, _age in weighted:
            n = (
                poll.sample_size
                if (poll.sample_size is not None and poll.sample_size > 0)
                else cfg.default_sample_size
            )
            s2 = (cfg.sampling_constant**2) / n
            share = weight / sum_w
            var_sampling_mean += (share**2) * s2

        variance = var_dispersion_mean + var_sampling_mean
        std_error = math.sqrt(variance) if variance > 0 else 0.0

        contributions = [
            PollContribution(
                poll_id=poll.poll_id,
                pollster=poll.pollster,
                field_end=poll.field_end,
                margin=poll.margin_dem_minus_rep,
                sample_size=poll.sample_size,
                age_days=age,
                weight_sample=w_sample,
                weight_recency=w_recency,
                weight_quality=w_quality,
                weight=weight,
                weight_share=weight / sum_w,
            )
            for (poll, w_sample, w_recency, w_quality, weight, age) in weighted
        ]
        contributions.sort(key=lambda c: c.weight_share, reverse=True)

        return AggregateResult(
            race_id=race_id,
            state_code=state_code,
            margin=margin,
            variance=variance,
            std_error=std_error,
            poll_count=len(polls),
            effective_sample_size=n_eff,
            last_updated=last_updated,
            reference_date=reference,
            method=cfg.method,
            contributions=contributions,
        )

    def aggregate_race(
        self,
        database: Database,
        race_id: str,
        *,
        state_code: str | None = None,
        reference_date: date | None = None,
    ) -> AggregateResult | None:
        """Read a race's polls from the database and aggregate them."""
        polls = database.polls.list_by_race(race_id)
        if state_code is None:
            race = database.senate_races.get(race_id)
            state_code = race.state_code if race is not None else None
        return self.aggregate(
            polls, race_id=race_id, state_code=state_code, reference_date=reference_date
        )

    def persist(self, database: Database, result: AggregateResult) -> PollAggregate:
        """Store an aggregate result as a ``poll_aggregates`` row (idempotent)."""
        entity = result.to_entity()
        database.poll_aggregates.upsert(entity)
        return entity


__all__ = [
    "SAMPLING_CONSTANT",
    "AggregationConfig",
    "PollContribution",
    "AggregateResult",
    "PollAggregator",
]
