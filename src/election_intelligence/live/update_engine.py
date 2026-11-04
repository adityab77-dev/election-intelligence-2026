"""Live update engine (Phase E).

Blends each battleground's stored poll forecast with its latest results snapshot
and runs the **unchanged** Monte Carlo engine to produce updated Senate control
probabilities, stored as a ``regime="live"`` simulation run.

The Monte Carlo engine is reused verbatim — this only changes the per-state
``StateForecast`` inputs it receives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from election_intelligence.data.ingestion.polls import BATTLEGROUND_RACES
from election_intelligence.data.storage.entities import SimRegime
from election_intelligence.live.results_blend import BlendConfig, blend_forecast
from election_intelligence.simulate import MonteCarloEngine, SimulationConfig
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from election_intelligence.data.storage.database import Database
    from election_intelligence.simulate import SimulationOutput

logger = get_logger(__name__)


def run_live_update(
    database: Database,
    *,
    seed: int = 2026,
    n_simulations: int = 50_000,
    code_version: str | None = None,
    blend_config: BlendConfig | None = None,
) -> SimulationOutput | None:
    """Blend polls + results and run a live Monte Carlo; store it as regime=live."""
    blended = []
    for code, race_id in BATTLEGROUND_RACES.items():
        poll_forecast = database.state_forecasts.latest_for_race(race_id)
        if poll_forecast is None:
            continue
        snapshot = database.reporting_snapshots.latest_for_race(race_id)
        blended.append(blend_forecast(poll_forecast, snapshot, blend_config))

    if not blended:
        logger.warning("live update: no forecasts available (run forecast first)")
        return None

    engine = MonteCarloEngine(
        SimulationConfig(n_simulations=n_simulations, random_seed=seed)
    )
    output = engine.simulate(blended, code_version=code_version)

    run = output.to_run()
    run.regime = SimRegime.LIVE  # mark as a live run (metadata only)
    run.trigger = "live-update"
    database.simulation_runs.upsert(run)
    database.simulation_results.upsert(output.to_result())
    logger.info(
        "live update stored: R %.0f%% / D %.0f%% / tie %.1f%%",
        output.prob_rep_control * 100,
        output.prob_dem_control * 100,
        output.prob_tie * 100,
    )
    return output


__all__ = ["run_live_update"]
