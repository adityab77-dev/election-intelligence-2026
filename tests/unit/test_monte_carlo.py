"""Unit tests for the Monte Carlo engine (requires numpy, not DuckDB)."""

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("numpy")

from election_intelligence.data.storage.entities import StateForecast  # noqa: E402
from election_intelligence.simulate import (  # noqa: E402
    MonteCarloEngine,
    SimulationConfig,
)

RACES = {
    "GA": "GA-2026",
    "NC": "NC-2026",
    "ME": "ME-2026",
    "MI": "MI-2026",
    "NH": "NH-2026",
    "TX": "TX-2026",
    "OH": "OH-2026-S",
    "IA": "IA-2026",
}


def _forecasts(mean: float, sigma: float = 4.0) -> list[StateForecast]:
    return [
        StateForecast(
            race_id=race_id,
            state_code=code,
            mean_margin=mean,
            sigma=sigma,
            confidence_level="Medium",
            poll_count=5,
            forecast_date=date(2026, 11, 1),
            inputs_hash="x",
        )
        for code, race_id in RACES.items()
    ]


CONFIG = SimulationConfig(n_simulations=20_000, random_seed=7)


@pytest.mark.unit
def test_probabilities_are_complementary() -> None:
    out = MonteCarloEngine(CONFIG).simulate(_forecasts(0.0))
    assert 0.0 <= out.prob_rep_control <= 1.0
    assert out.prob_rep_control + out.prob_dem_control == pytest.approx(1.0)


@pytest.mark.unit
def test_expected_seats_sum_to_100() -> None:
    out = MonteCarloEngine(CONFIG).simulate(_forecasts(0.0))
    assert out.expected_rep_seats + out.expected_dem_seats == pytest.approx(100.0)


@pytest.mark.unit
def test_strong_dem_lead_gives_republicans_low_control() -> None:
    out = MonteCarloEngine(CONFIG).simulate(_forecasts(20.0))  # D +20 everywhere
    assert out.prob_rep_control < 0.05


@pytest.mark.unit
def test_strong_rep_lead_gives_republicans_high_control() -> None:
    out = MonteCarloEngine(CONFIG).simulate(_forecasts(-20.0))  # R +20 everywhere
    assert out.prob_rep_control > 0.95


@pytest.mark.unit
def test_seat_bounds_and_histogram() -> None:
    out = MonteCarloEngine(CONFIG).simulate(_forecasts(0.0))
    assert out.rep_seats_p10 >= 48  # baseline R seats
    assert out.rep_seats_p90 <= 56  # baseline + 8 battlegrounds
    assert sum(out.seat_histogram.values()) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.unit
def test_reproducible_with_fixed_seed() -> None:
    a = MonteCarloEngine(CONFIG).simulate(_forecasts(1.0))
    b = MonteCarloEngine(CONFIG).simulate(_forecasts(1.0))
    assert a.prob_rep_control == b.prob_rep_control
    assert a.expected_rep_seats == b.expected_rep_seats
    assert a.inputs_hash == b.inputs_hash
    assert a.seat_histogram == b.seat_histogram


@pytest.mark.unit
def test_different_seed_changes_draws() -> None:
    a = MonteCarloEngine(SimulationConfig(n_simulations=20_000, random_seed=1))
    b = MonteCarloEngine(SimulationConfig(n_simulations=20_000, random_seed=2))
    # Same inputs, different seed -> distinct run ids (seed is in the hash).
    assert a.simulate(_forecasts(0.5)).run_id != b.simulate(_forecasts(0.5)).run_id


@pytest.mark.unit
def test_diagnostics_and_influential_states() -> None:
    out = MonteCarloEngine(CONFIG).simulate(_forecasts(0.0))
    assert out.mc_std_error > 0.0
    assert out.convergence_delta >= 0.0
    assert len(out.influential_states) == len(RACES)
    assert all("leverage" in s for s in out.influential_states)


@pytest.mark.unit
def test_empty_forecasts_raises() -> None:
    with pytest.raises(ValueError):
        MonteCarloEngine(CONFIG).simulate([])
