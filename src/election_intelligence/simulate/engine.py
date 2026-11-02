"""Correlated Monte Carlo simulator and Senate control model (Phase 6).

Consumes the Phase 5 per-state forecast distributions and produces the Senate
control probability by drawing correlated state outcomes:

    total_margin_s = mean_margin_s + national_error + state_error_s

The national error is a single draw per simulation shared across all states
(the correlated polling miss); the state error is independent per state. The
forecast's total sigma is split into a shared national component and an
independent state component, so correlation is introduced without inflating the
marginal uncertainty.

Determinism: with a fixed seed the draws, and therefore every reported number,
are identical across runs. Only the eight battleground races are simulated; all
other seats are a configurable baseline (an MVP assumption to be replaced when
the full Senate roster is loaded).

Scope: no election-night logic, no fundamentals, no narratives.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from election_intelligence.data.storage.entities import (
    RunStatus,
    SimRegime,
    SimulationResult,
    SimulationRun,
    StateForecast,
)
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from election_intelligence.data.storage.database import Database

logger = get_logger(__name__)


@dataclass(frozen=True)
class SimulationConfig:
    """Parameters controlling the simulation."""

    n_simulations: int = 50_000
    random_seed: int = 2026
    # Shared national-error standard deviation (points). The forecast sigma is
    # split into this correlated component plus an independent state component.
    national_sigma: float = 3.0
    state_sigma_floor: float = 0.5
    # Seats not simulated (MVP baseline; 53-47 minus the eight battlegrounds'
    # current holders: R holds 5 of them, D holds 3).
    baseline_rep_seats: int = 48
    baseline_dem_seats: int = 44
    rep_control_threshold: int = 50  # R controls at 50 via the VP tiebreak
    method: str = "mc_v1"


@dataclass(frozen=True)
class SimulationOutput:
    """Full result of one simulation run (in-memory, before persistence)."""

    run_id: str
    inputs_hash: str
    n_simulations: int
    random_seed: int
    code_version: str | None
    generated_at: datetime
    race_ids: list[str]
    prob_rep_control: float
    prob_dem_control: float
    prob_undetermined: float
    expected_rep_seats: float
    expected_dem_seats: float
    rep_seats_median: int
    rep_seats_p10: int
    rep_seats_p90: int
    seat_histogram: dict[str, float]
    mc_std_error: float  # percentage points
    convergence_delta: float  # percentage points
    influential_states: list[dict[str, Any]]
    method: str = "mc_v1"

    def to_run(self) -> SimulationRun:
        return SimulationRun(
            run_id=self.run_id,
            regime=SimRegime.PRE_ELECTION,
            n_simulations=self.n_simulations,
            random_seed=self.random_seed,
            inputs_hash=self.inputs_hash,
            code_version=self.code_version,
            trigger="simulate",
            status=RunStatus.COMPLETED,
            started_at=self.generated_at,
            finished_at=self.generated_at,
        )

    def to_result(self) -> SimulationResult:
        return SimulationResult(
            run_id=self.run_id,
            prob_rep_control=self.prob_rep_control,
            prob_dem_control=self.prob_dem_control,
            prob_undetermined=self.prob_undetermined,
            mc_std_error=self.mc_std_error,
            rep_seats_median=self.rep_seats_median,
            rep_seats_p10=self.rep_seats_p10,
            rep_seats_p90=self.rep_seats_p90,
            seat_histogram=dict(self.seat_histogram),
            expected_rep_seats=self.expected_rep_seats,
            expected_dem_seats=self.expected_dem_seats,
            convergence_delta=self.convergence_delta,
            influential_states=list(self.influential_states),
        )


class MonteCarloEngine:
    """Runs the correlated Monte Carlo and computes control probabilities."""

    def __init__(self, config: SimulationConfig | None = None) -> None:
        self._cfg = config or SimulationConfig()

    @property
    def config(self) -> SimulationConfig:
        return self._cfg

    def _inputs_hash(self, forecasts: list[StateForecast]) -> str:
        cfg = self._cfg
        parts = [
            f"{fc.race_id}:{fc.mean_margin:.6f}:{fc.sigma:.6f}"
            for fc in sorted(forecasts, key=lambda f: f.race_id)
        ]
        payload = "|".join(parts) + (
            f"|n={cfg.n_simulations}|seed={cfg.random_seed}"
            f"|nat={cfg.national_sigma}|br={cfg.baseline_rep_seats}"
            f"|bd={cfg.baseline_dem_seats}|m={cfg.method}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def simulate(
        self, forecasts: list[StateForecast], *, code_version: str | None = None
    ) -> SimulationOutput:
        """Run the simulation over the given forecasts."""
        if not forecasts:
            raise ValueError("simulate() requires at least one StateForecast")

        import numpy as np

        cfg = self._cfg
        n = cfg.n_simulations
        k = len(forecasts)

        means = np.array([fc.mean_margin for fc in forecasts], dtype=float)
        sigma = np.array([fc.sigma for fc in forecasts], dtype=float)
        # Split total sigma into shared national + independent state components.
        state_var = sigma**2 - cfg.national_sigma**2
        state_sigma = np.sqrt(np.maximum(state_var, cfg.state_sigma_floor**2))

        rng = np.random.default_rng(cfg.random_seed)
        national = rng.normal(0.0, cfg.national_sigma, size=(n, 1))
        state_noise = rng.standard_normal((n, k)) * state_sigma

        margins = means[np.newaxis, :] + national + state_noise
        dem_wins = margins > 0.0  # margin is D - R; positive favours D
        rep_wins = ~dem_wins

        rep_won = rep_wins.sum(axis=1)
        rep_total = cfg.baseline_rep_seats + rep_won
        total_seats = cfg.baseline_rep_seats + cfg.baseline_dem_seats + k
        if total_seats != 100:  # pragma: no cover - MVP sanity log
            logger.debug("total seats = %d (expected 100 with 8 battlegrounds)", total_seats)

        rep_control = rep_total >= cfg.rep_control_threshold
        prob_rep = float(rep_control.mean())
        prob_dem = 1.0 - prob_rep

        expected_rep = float(rep_total.mean())
        expected_dem = float(total_seats - expected_rep)

        percentiles = np.percentile(rep_total, [10, 50, 90])
        p10, median, p90 = (int(round(float(x))) for x in percentiles)

        seats, counts = np.unique(rep_total, return_counts=True)
        histogram = {str(int(s)): float(c) / n for s, c in zip(seats, counts, strict=True)}

        mc_std_error = 100.0 * math.sqrt(prob_rep * (1.0 - prob_rep) / n)

        half = n // 2
        p_first = float((rep_total[:half] >= cfg.rep_control_threshold).mean())
        p_second = float((rep_total[half:] >= cfg.rep_control_threshold).mean())
        convergence_delta = 100.0 * abs(p_first - p_second)

        influential = self._influential_states(forecasts, rep_wins, rep_control)

        inputs_hash = self._inputs_hash(forecasts)
        return SimulationOutput(
            run_id=f"mc-{inputs_hash}",
            inputs_hash=inputs_hash,
            n_simulations=n,
            random_seed=cfg.random_seed,
            code_version=code_version,
            generated_at=datetime.now(timezone.utc),
            race_ids=[fc.race_id for fc in forecasts],
            prob_rep_control=prob_rep,
            prob_dem_control=prob_dem,
            prob_undetermined=0.0,
            expected_rep_seats=expected_rep,
            expected_dem_seats=expected_dem,
            rep_seats_median=median,
            rep_seats_p10=p10,
            rep_seats_p90=p90,
            seat_histogram=histogram,
            mc_std_error=mc_std_error,
            convergence_delta=convergence_delta,
            influential_states=influential,
            method=cfg.method,
        )

    @staticmethod
    def _influential_states(
        forecasts: list[StateForecast], rep_wins: Any, rep_control: Any
    ) -> list[dict[str, Any]]:
        """Control leverage: P(R control | R wins s) - P(R control | D wins s)."""
        influential: list[dict[str, Any]] = []
        for index, fc in enumerate(forecasts):
            won = rep_wins[:, index]
            lost = ~won
            p_given_r = float(rep_control[won].mean()) if won.any() else None
            p_given_d = float(rep_control[lost].mean()) if lost.any() else None
            leverage = (
                p_given_r - p_given_d
                if p_given_r is not None and p_given_d is not None
                else 0.0
            )
            influential.append(
                {
                    "state": fc.state_code or fc.race_id,
                    "race_id": fc.race_id,
                    "leverage": round(leverage, 4),
                }
            )
        influential.sort(key=lambda item: item["leverage"], reverse=True)
        return influential

    def run_and_store(
        self,
        database: Database,
        forecasts: list[StateForecast],
        *,
        code_version: str | None = None,
    ) -> SimulationOutput:
        """Simulate, then persist the run and its result (idempotent by inputs)."""
        output = self.simulate(forecasts, code_version=code_version)
        database.simulation_runs.upsert(output.to_run())
        database.simulation_results.upsert(output.to_result())
        return output


__all__ = [
    "SimulationConfig",
    "SimulationOutput",
    "MonteCarloEngine",
]
