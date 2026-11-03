"""Unit tests for dashboard formatting helpers (no streamlit required)."""

from __future__ import annotations

import pytest

from election_intelligence.dashboard.app import _fmt_margin, _p_dem, _rating


@pytest.mark.unit
@pytest.mark.parametrize(
    ("margin", "expected"),
    [
        (1.8, "D +1.8"),
        (-2.4, "R +2.4"),
        (0.0, "D +0.0"),
        (-0.2, "R +0.2"),
    ],
)
def test_fmt_margin(margin: float, expected: str) -> None:
    assert _fmt_margin(margin) == expected


@pytest.mark.unit
def test_win_probability_and_rating() -> None:
    # A solid D lead -> high P(D) -> Strong/Lean D; a tied race -> Toss-Up.
    assert _p_dem(8.0, 4.0) > 0.95
    assert _rating(_p_dem(8.0, 4.0)) in {"Strong D", "Lean D"}
    assert _rating(_p_dem(0.0, 4.0)) == "Toss-Up"
    assert _rating(_p_dem(-8.0, 4.0)) in {"Strong R", "Lean R"}
