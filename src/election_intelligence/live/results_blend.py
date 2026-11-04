"""Poll-to-results transition blend (Phase E).

Turns a poll-based `StateForecast` plus the latest `ReportingSnapshot` into a
*live* `StateForecast` — the same type the Monte Carlo engine already consumes.
The results weight rises with percent reporting:

    w = percent_reporting / 100
    live_mean  = (1 - w)*poll_mean + w*counted_margin
    live_sigma = max((1 - w)*poll_sigma, floor)

`w = 0` → polls only; `w = 1` → counted margin replaces the forecast. Called
races are pinned near-certain. This is a pure transform — it changes only the
*inputs* fed to the unchanged Monte Carlo engine.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from election_intelligence.data.storage.entities import (
    Party,
    ReportingSnapshot,
    StateForecast,
)


@dataclass(frozen=True)
class BlendConfig:
    sigma_floor: float = 0.75
    called_margin: float = 30.0  # pinned margin magnitude for a called race
    called_sigma: float = 0.2
    method: str = "live_blend_v1"


def _inputs_hash(race_id: str, mean: float, sigma: float, pct: float) -> str:
    payload = f"{race_id}|{mean:.4f}|{sigma:.4f}|{pct:.2f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def blend_forecast(
    poll_forecast: StateForecast,
    snapshot: ReportingSnapshot | None,
    config: BlendConfig | None = None,
) -> StateForecast:
    """Blend a poll forecast with live results into a live `StateForecast`."""
    cfg = config or BlendConfig()

    # No results yet -> 100% polls.
    if snapshot is None or snapshot.percent_reporting <= 0.0:
        return poll_forecast

    w = min(max(snapshot.percent_reporting / 100.0, 0.0), 1.0)
    if snapshot.is_called and snapshot.called_party is not None:
        direction = 1.0 if snapshot.called_party is Party.DEM else -1.0
        mean = direction * cfg.called_margin
        sigma = cfg.called_sigma
    else:
        results_margin = (
            snapshot.margin if snapshot.margin is not None else poll_forecast.mean_margin
        )
        mean = (1.0 - w) * poll_forecast.mean_margin + w * results_margin
        sigma = max((1.0 - w) * poll_forecast.sigma, cfg.sigma_floor)

    return StateForecast(
        forecast_id=f"{poll_forecast.race_id}:live:{cfg.method}",
        race_id=poll_forecast.race_id,
        state_code=poll_forecast.state_code,
        mean_margin=mean,
        sigma=sigma,
        confidence_level=poll_forecast.confidence_level,
        poll_count=poll_forecast.poll_count,
        forecast_date=poll_forecast.forecast_date,
        method=cfg.method,
        inputs_hash=_inputs_hash(poll_forecast.race_id, mean, sigma, w * 100.0),
    )


__all__ = ["BlendConfig", "blend_forecast"]
