"""Unit tests for the candidate->party and pollster-grade layers."""

from __future__ import annotations

import pytest

from election_intelligence.data.ingestion.party_mapping import (
    candidate_name,
    party_from_header,
)
from election_intelligence.data.ingestion.pollster_grades import grade_for
from election_intelligence.data.storage.entities import Party


@pytest.mark.unit
def test_party_from_header_suffix() -> None:
    assert party_from_header("Jon Ossoff (D)") is Party.DEM
    assert party_from_header("Mike Collins (R)") is Party.REP
    assert party_from_header("Generic Republican") is Party.REP
    assert party_from_header("Other") is None
    assert party_from_header("Undecided") is None


@pytest.mark.unit
def test_candidate_name_strips_suffix_and_footnotes() -> None:
    assert candidate_name("Jon Ossoff (D)[a]") == "Jon Ossoff"


@pytest.mark.unit
def test_grade_lookup() -> None:
    assert grade_for("Emerson College") == "B+"
    assert grade_for("Siena College") == "A+"
    # Canonicalization: footnotes / lean tags ignored.
    assert grade_for("InsiderAdvantage (R)[124]") == "B"
    # Unknown -> None -> aggregation engine applies its neutral default.
    assert grade_for("Totally Unknown Pollster") is None
