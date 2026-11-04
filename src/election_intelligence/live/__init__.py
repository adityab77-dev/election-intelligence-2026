"""Election-night live regime (Phase E).

Blends poll forecasts with real results by percent reporting, then reruns the
unchanged Monte Carlo engine. The aggregation, forecast, and Monte Carlo engines
are not modified — only the per-state inputs change.
"""

from __future__ import annotations

from election_intelligence.live.results_blend import BlendConfig, blend_forecast
from election_intelligence.live.update_engine import run_live_update

__all__ = ["BlendConfig", "blend_forecast", "run_live_update"]
