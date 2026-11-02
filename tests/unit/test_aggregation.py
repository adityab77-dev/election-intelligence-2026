"""Unit tests for the aggregation engine math (no database required).

Each test isolates one weighting effect by holding the other two constant, so
the weighted margin has a known closed-form value.
"""

from __future__ import annotations

from datetime import date

import pytest

from election_intelligence.aggregation import PollAggregator
from election_intelligence.data.storage.entities import Poll


def _poll(margin: float, *, n: int = 800, grade: str = "A", end: date) -> Poll:
    return Poll(
        race_id="GA-2026",
        pollster="Test",
        pollster_grade=grade,
        field_end=end,
        sample_size=n,
        population="LV",
        margin_dem_minus_rep=margin,
    )


AGG = PollAggregator()
D = date(2026, 10, 20)


@pytest.mark.unit
def test_sample_size_weighting_pulls_toward_larger_poll() -> None:
    # Same date, same grade -> only sample size differs.
    polls = [_poll(0.0, n=400, end=D), _poll(3.0, n=900, end=D)]
    result = AGG.aggregate(polls, race_id="GA-2026")
    # sqrt(400)=20, sqrt(900)=30 -> (20*0 + 30*3)/50 = 1.8  (simple mean is 1.5)
    assert result is not None
    assert result.margin == pytest.approx(1.8)


@pytest.mark.unit
def test_quality_weighting_pulls_toward_higher_grade() -> None:
    polls = [_poll(4.0, grade="A+", end=D), _poll(0.0, grade="F", end=D)]
    result = AGG.aggregate(polls, race_id="GA-2026")
    # weights 1.0 vs 0.1 -> 4*1.0 / 1.1 = 3.636  (simple mean is 2.0)
    assert result.margin == pytest.approx(4.0 / 1.1)
    assert result.margin > 2.0


@pytest.mark.unit
def test_recency_weighting_pulls_toward_newer_poll() -> None:
    newer = _poll(4.0, end=date(2026, 10, 20))
    older = _poll(0.0, end=date(2026, 10, 6))  # exactly one half-life earlier
    result = AGG.aggregate([newer, older], race_id="GA-2026")
    # recency 1.0 vs 0.5 -> 4*1.0 / 1.5 = 2.667  (simple mean is 2.0)
    assert result.margin == pytest.approx(4.0 / 1.5)
    assert result.margin > 2.0


@pytest.mark.unit
def test_weight_shares_sum_to_one() -> None:
    polls = [_poll(1.0, end=D), _poll(2.0, n=1000, grade="B", end=date(2026, 10, 10))]
    result = AGG.aggregate(polls, race_id="GA-2026")
    assert sum(c.weight_share for c in result.contributions) == pytest.approx(1.0)


@pytest.mark.unit
def test_variance_and_metadata() -> None:
    polls = [_poll(1.0, end=D), _poll(3.0, end=date(2026, 10, 14))]
    result = AGG.aggregate(polls, race_id="GA-2026", state_code="GA")
    assert result.variance >= 0.0
    assert result.std_error == pytest.approx(result.variance**0.5)
    assert result.poll_count == 2
    assert result.last_updated == D
    assert result.state_code == "GA"


@pytest.mark.unit
def test_empty_polls_returns_none() -> None:
    assert AGG.aggregate([], race_id="GA-2026") is None


@pytest.mark.unit
def test_single_poll_has_positive_variance() -> None:
    # One poll -> no dispersion, but sampling variance keeps it > 0.
    result = AGG.aggregate([_poll(2.0, n=800, end=D)], race_id="GA-2026")
    assert result.poll_count == 1
    assert result.variance > 0.0
