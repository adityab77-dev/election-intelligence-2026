"""Unit tests for the poll-to-results blend (no database required)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from election_intelligence.data.storage.entities import (
    Party,
    ReportingSnapshot,
    StateForecast,
)
from election_intelligence.live import blend_forecast


def _poll(mean: float = 2.0, sigma: float = 4.0) -> StateForecast:
    return StateForecast(
        race_id="GA-2026", state_code="GA", mean_margin=mean, sigma=sigma,
        confidence_level="Medium", poll_count=5, forecast_date=date(2026, 11, 3),
        inputs_hash="x",
    )


def _snap(pct: float, margin: float = 8.0, called: bool = False) -> ReportingSnapshot:
    return ReportingSnapshot(
        race_id="GA-2026", source="wikipedia",
        reported_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        percent_reporting=pct, total_votes=1000, dem_votes=540, rep_votes=460,
        margin=margin, leader_party=Party.DEM, is_called=called,
        called_party=Party.DEM if called else None,
    )


@pytest.mark.unit
def test_no_results_returns_poll_forecast() -> None:
    poll = _poll(2.0)
    assert blend_forecast(poll, None) is poll
    assert blend_forecast(poll, _snap(0.0)).mean_margin == pytest.approx(2.0)


@pytest.mark.unit
def test_half_reporting_blends_50_50() -> None:
    out = blend_forecast(_poll(2.0), _snap(50.0, margin=8.0))
    assert out.mean_margin == pytest.approx(0.5 * 2.0 + 0.5 * 8.0)  # 5.0


@pytest.mark.unit
def test_full_reporting_uses_results() -> None:
    out = blend_forecast(_poll(2.0), _snap(100.0, margin=8.0))
    assert out.mean_margin == pytest.approx(8.0, abs=1e-6)
    assert out.sigma <= 1.0  # collapsed to the floor


@pytest.mark.unit
def test_sigma_shrinks_with_reporting() -> None:
    assert blend_forecast(_poll(), _snap(50.0)).sigma < _poll().sigma
    assert blend_forecast(_poll(), _snap(90.0)).sigma < blend_forecast(_poll(), _snap(50.0)).sigma


@pytest.mark.unit
def test_called_race_is_pinned() -> None:
    out = blend_forecast(_poll(2.0), _snap(95.0, called=True))
    assert out.mean_margin > 20  # pinned toward the Democratic winner
    assert out.sigma < 1.0


@pytest.mark.unit
def test_method_label_is_live() -> None:
    assert blend_forecast(_poll(), _snap(50.0)).method == "live_blend_v1"
