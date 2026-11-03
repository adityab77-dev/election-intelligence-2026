"""Unit tests for poll-row normalization helpers (no deps beyond stdlib)."""

from __future__ import annotations

from datetime import date

import pytest

from election_intelligence.data.ingestion.normalization import (
    clean_pollster,
    parse_date_range,
    parse_pct,
    parse_sample,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("October 31 – November 2, 2026", date(2026, 10, 31), date(2026, 11, 2)),
        ("May 16–17, 2026", date(2026, 5, 16), date(2026, 5, 17)),
        ("April 28 – May 2, 2026", date(2026, 4, 28), date(2026, 5, 2)),
        ("November 2, 2026", date(2026, 11, 2), date(2026, 11, 2)),
        ("through October 20, 2026", date(2026, 10, 20), date(2026, 10, 20)),
    ],
)
def test_parse_date_range(text: str, start: date, end: date) -> None:
    assert parse_date_range(text) == (start, end)


@pytest.mark.unit
def test_parse_date_range_strips_footnotes() -> None:
    _start, end = parse_date_range("October 31 – November 2, 2026[a]")
    assert end == date(2026, 11, 2)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "size", "pop"),
    [("2,500 (LV)", 2500, "LV"), ("624 (RV)", 624, "RV"), ("1,000 (LV)", 1000, "LV")],
)
def test_parse_sample(text: str, size: int, pop: str) -> None:
    assert parse_sample(text) == (size, pop)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "value"),
    [("53%", 53.0), ("14.8%", 14.8), ("2%[h]", 2.0), ("—", None)],
)
def test_parse_pct(text: str, value: float | None) -> None:
    assert parse_pct(text) == value


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("InsiderAdvantage (R)[124]", "InsiderAdvantage"),
        ("Emerson College[62][C]", "Emerson College"),
        ("University of Georgia[58][A]", "University of Georgia"),
    ],
)
def test_clean_pollster(text: str, expected: str) -> None:
    assert clean_pollster(text) == expected
