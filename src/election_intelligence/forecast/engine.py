"""Senate forecast engine (Phase 5).

Turns a weighted poll aggregate (Phase 4) into a per-state forecast
distribution ``StateForecast(mean_margin, sigma, confidence_level, ...)``,
modelling each race's margin as ``Normal(mean_margin, sigma)``.

Scope (MVP): polls only. There is **no fundamentals prior, no Monte Carlo, and
no win-probability output** here. The mean is the weighted poll margin; the
sigma inflates the aggregate's variance with a systematic polling-miss floor
and penalties for thin and stale polling.

Reproducibility: the engine is deterministic, and every forecast records an
``inputs_hash`` over the inputs that produced it, so the same aggregate and
forecast date always yield the same forecast.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from election_intelligence.aggregation import AggregateResult, PollAggregator
from election_intelligence.data.storage.entities import ConfidenceLevel, StateForecast
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from election_intelligence.data.storage.database import Database

logger = get_logger(__name__)


@dataclass(frozen=True)
class ForecastConfig:
    """Tunable parameters for turning an aggregate into a distribution."""

    # Systematic polling-miss floor (points) added in quadrature. Historical
    # midterm Senate polling misses run ~3-5 points.
    base_polling_miss: float = 3.5
    # Below this many polls, add a per-missing-poll uncertainty penalty.
    min_polls_full: int = 3
    count_penalty_per_missing_poll: float = 1.5
    # Extra sigma per week between the latest poll and the forecast date.
    staleness_sigma_per_week: float = 0.5
    # Confidence-label thresholds.
    high_confidence_sigma: float = 3.5
    low_confidence_sigma: float = 5.0
    min_polls_for_nonlow: int = 2
    method: str = "poll_only_v1"


class ForecastEngine:
    """Produces per-state forecast distributions from poll aggregates."""

    def __init__(self, config: ForecastConfig | None = None) -> None:
        self._cfg = config or ForecastConfig()

    @property
    def config(self) -> ForecastConfig:
        return self._cfg

    def _sigma(self, aggregate: AggregateResult, forecast_date: date) -> float:
        cfg = self._cfg
        poll_variance = max(aggregate.variance, 0.0)
        base_variance = cfg.base_polling_miss**2

        missing = max(0, cfg.min_polls_full - aggregate.poll_count)
        count_penalty = cfg.count_penalty_per_missing_poll * missing

        days_stale = max(0, (forecast_date - aggregate.last_updated).days)
        staleness = cfg.staleness_sigma_per_week * (days_stale / 7.0)

        return math.sqrt(
            poll_variance + base_variance + count_penalty**2 + staleness**2
        )

    def _confidence(self, sigma: float, poll_count: int) -> ConfidenceLevel:
        cfg = self._cfg
        if poll_count < cfg.min_polls_for_nonlow or sigma > cfg.low_confidence_sigma:
            return ConfidenceLevel.LOW
        if sigma <= cfg.high_confidence_sigma and poll_count >= cfg.min_polls_full:
            return ConfidenceLevel.HIGH
        return ConfidenceLevel.MEDIUM

    def _inputs_hash(self, aggregate: AggregateResult, forecast_date: date) -> str:
        cfg = self._cfg
        payload = "|".join(
            [
                aggregate.race_id,
                f"{aggregate.margin:.6f}",
                f"{aggregate.variance:.6f}",
                str(aggregate.poll_count),
                aggregate.last_updated.isoformat(),
                forecast_date.isoformat(),
                cfg.method,
                f"{cfg.base_polling_miss:.6f}",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def forecast(
        self, aggregate: AggregateResult, *, forecast_date: date | None = None
    ) -> StateForecast:
        """Build a forecast distribution from a poll aggregate."""
        cfg = self._cfg
        fdate = forecast_date or date.today()
        sigma = self._sigma(aggregate, fdate)
        confidence = self._confidence(sigma, aggregate.poll_count)
        inputs_hash = self._inputs_hash(aggregate, fdate)
        forecast_id = f"{aggregate.race_id}:{fdate.isoformat()}:{cfg.method}"
        return StateForecast(
            forecast_id=forecast_id,
            race_id=aggregate.race_id,
            state_code=aggregate.state_code,
            mean_margin=aggregate.margin,
            sigma=sigma,
            confidence_level=confidence,
            poll_count=aggregate.poll_count,
            forecast_date=fdate,
            method=cfg.method,
            inputs_hash=inputs_hash,
        )

    def forecast_race(
        self,
        database: Database,
        race_id: str,
        *,
        state_code: str | None = None,
        forecast_date: date | None = None,
        aggregator: PollAggregator | None = None,
    ) -> StateForecast | None:
        """Aggregate a race's polls and produce its forecast; ``None`` if no polls."""
        aggregator = aggregator or PollAggregator()
        aggregate = aggregator.aggregate_race(database, race_id, state_code=state_code)
        if aggregate is None:
            return None
        return self.forecast(aggregate, forecast_date=forecast_date)

    def persist(self, database: Database, forecast: StateForecast) -> StateForecast:
        """Store a forecast (idempotent per race/date/method)."""
        database.state_forecasts.upsert(forecast)
        return forecast


__all__ = ["ForecastConfig", "ForecastEngine"]
