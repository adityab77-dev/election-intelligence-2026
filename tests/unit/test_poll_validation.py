"""Unit tests for poll validation (no database required)."""

from __future__ import annotations

from datetime import date

import pytest

from election_intelligence.data.ingestion.polls import validate_poll
from election_intelligence.data.storage.entities import Poll


def _poll(**overrides: object) -> Poll:
    base = {
        "race_id": "GA-2026",
        "pollster": "Example",
        "field_start": date(2026, 10, 10),
        "field_end": date(2026, 10, 14),
        "sample_size": 800,
        "population": "LV",
        "margin_dem_minus_rep": 1.5,
    }
    base.update(overrides)
    return Poll.model_validate(base)


@pytest.mark.unit
def test_valid_poll_has_no_errors() -> None:
    assert validate_poll(_poll()) == []


@pytest.mark.unit
def test_race_outside_battleground_is_rejected() -> None:
    errors = validate_poll(_poll(race_id="CA-2026"))
    assert any("battleground" in e for e in errors)


@pytest.mark.unit
def test_field_end_after_election_is_rejected() -> None:
    errors = validate_poll(_poll(field_end=date(2026, 11, 10)))
    assert any("after election" in e for e in errors)


@pytest.mark.unit
def test_field_start_after_field_end_is_rejected() -> None:
    errors = validate_poll(
        _poll(field_start=date(2026, 10, 20), field_end=date(2026, 10, 14))
    )
    assert any("field_start" in e for e in errors)


@pytest.mark.unit
def test_nonpositive_sample_size_is_rejected() -> None:
    assert any("sample_size" in e for e in validate_poll(_poll(sample_size=0)))


@pytest.mark.unit
def test_out_of_range_margin_is_rejected() -> None:
    assert any("margin" in e for e in validate_poll(_poll(margin_dem_minus_rep=250.0)))
