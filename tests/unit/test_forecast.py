"""Unit tests for the forecast engine (no database required)."""

from __future__ import annotations

import math
from datetime import date

import pytest

from election_intelligence.aggregation.engine import AggregateResult
from election_intelligence.data.storage.entities import ConfidenceLevel
from election_intelligence.forecast import ForecastEngine

ENGINE = ForecastEngine()
FD = date(2026, 11, 1)


def _aggregate(
    margin: float,
    variance: float,
    poll_count: int,
    *,
    last: date = date(2026, 10, 29),
    state: str = "GA",
) -> AggregateResult:
    return AggregateResult(
        race_id="GA-2026",
        state_code=state,
        margin=margin,
        variance=variance,
        std_error=math.sqrt(variance),
        poll_count=poll_count,
        effective_sample_size=float(poll_count),
        last_updated=last,
        reference_date=last,
        method="weighted_v1",
        contributions=[],
    )


@pytest.mark.unit
def test_mean_margin_passes_through() -> None:
    forecast = ENGINE.forecast(_aggregate(1.83, 3.46, 5), forecast_date=FD)
    assert forecast.mean_margin == pytest.approx(1.83)


@pytest.mark.unit
def test_sigma_includes_base_polling_miss() -> None:
    # variance 3.46 + base 3.5^2 + ~3 days staleness -> ~3.97
    forecast = ENGINE.forecast(_aggregate(1.83, 3.46, 5), forecast_date=FD)
    assert forecast.sigma == pytest.approx(3.97, abs=0.05)
    # sigma must exceed the aggregate's own uncertainty (base miss added).
    assert forecast.sigma > math.sqrt(3.46)


@pytest.mark.unit
def test_confidence_medium_for_typical_tossup() -> None:
    forecast = ENGINE.forecast(_aggregate(1.83, 3.46, 5), forecast_date=FD)
    assert forecast.confidence_level is ConfidenceLevel.MEDIUM


@pytest.mark.unit
def test_confidence_low_for_thin_polling() -> None:
    forecast = ENGINE.forecast(_aggregate(0.0, 16.0, 1), forecast_date=FD)
    assert forecast.confidence_level is ConfidenceLevel.LOW


@pytest.mark.unit
def test_confidence_high_when_tight_and_fresh() -> None:
    # No dispersion, fresh (forecast_date == last) -> sigma == base == 3.5 -> High.
    forecast = ENGINE.forecast(
        _aggregate(2.0, 0.0, 5, last=FD), forecast_date=FD
    )
    assert forecast.sigma == pytest.approx(3.5)
    assert forecast.confidence_level is ConfidenceLevel.HIGH


@pytest.mark.unit
def test_thin_polling_has_larger_sigma_than_rich() -> None:
    thin = ENGINE.forecast(_aggregate(1.0, 4.0, 1), forecast_date=FD)
    rich = ENGINE.forecast(_aggregate(1.0, 4.0, 6), forecast_date=FD)
    assert thin.sigma > rich.sigma


@pytest.mark.unit
def test_forecast_is_reproducible() -> None:
    agg = _aggregate(1.83, 3.46, 5)
    a = ENGINE.forecast(agg, forecast_date=FD)
    b = ENGINE.forecast(agg, forecast_date=FD)
    assert a.inputs_hash == b.inputs_hash
    assert a.sigma == b.sigma
    assert a.forecast_id == b.forecast_id == "GA-2026:2026-11-01:poll_only_v1"
