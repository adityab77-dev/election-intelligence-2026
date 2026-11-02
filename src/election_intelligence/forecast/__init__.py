"""Pre-election forecasting regime (Phase 5 — Senate Forecast Engine).

Consumes the Phase 4 weighted poll aggregate and produces a per-state forecast
distribution (``StateForecast``: mean margin, sigma, confidence). Deterministic;
polls only (no fundamentals, no Monte Carlo, no win probabilities).
"""

from __future__ import annotations

from election_intelligence.forecast.engine import ForecastConfig, ForecastEngine

__all__ = ["ForecastConfig", "ForecastEngine"]
