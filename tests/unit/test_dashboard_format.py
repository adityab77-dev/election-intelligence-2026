"""Unit tests for dashboard formatting helpers (no streamlit required)."""

from __future__ import annotations

import pytest

from election_intelligence.dashboard.app import _format_margin


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
def test_format_margin(margin: float, expected: str) -> None:
    assert _format_margin(margin) == expected
