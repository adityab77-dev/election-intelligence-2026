"""Unit tests for the Clarity results parser (no network/DB)."""

from __future__ import annotations

import pytest

pytest.importorskip("pandas")  # ClarityResultsSource imports the results package

from election_intelligence.data.ingestion.results import ClarityResultsSource  # noqa: E402
from election_intelligence.data.ingestion.results.clarity import decode_body  # noqa: E402
from election_intelligence.data.storage.entities import Party  # noqa: E402

SENATE = {
    "SUBCAT": "United States Senate",
    "C": "United States Senator",
    "CH": ["Ashley Hinson", "Josh Turek", "Thomas Laehn", "Write-in"],
    "P": ["REP", "DEM", "LIB", ""],
    "V": [164420, 218101, 10232, 520],
    "PCT": [41.0, 54.3, 2.5, 0.1],
    "T": [393273],
    "TP": 99,
    "PR": 11,
    "W": [0, 0, 0, 0],
}
GOVERNOR = {"SUBCAT": "Governor", "C": "Governor", "CH": ["A", "B"],
            "P": ["REP", "DEM"], "V": [100, 90], "T": [190], "TP": 99, "PR": 11, "W": [0, 0]}


@pytest.mark.unit
def test_parse_senate_contest() -> None:
    result = ClarityResultsSource().parse_senate([GOVERNOR, SENATE], "IA-2026", "IA")
    assert result is not None
    snap = result.snapshot
    assert snap.dem_votes == 218101 and snap.rep_votes == 164420
    assert snap.total_votes == 393273
    assert snap.leader_party is Party.DEM
    assert snap.margin == pytest.approx((218101 - 164420) / 393273 * 100, abs=0.1)
    assert snap.percent_reporting == pytest.approx(11 / 99 * 100, abs=0.1)
    assert len(result.candidates) == 4
    assert not snap.is_called


@pytest.mark.unit
def test_no_senate_contest_returns_none() -> None:
    assert ClarityResultsSource().parse_senate([GOVERNOR], "IA-2026", "IA") is None


@pytest.mark.unit
def test_winner_flag_marks_called() -> None:
    called = dict(SENATE, W=[0, 1, 0, 0])  # Turek (DEM) flagged winner
    result = ClarityResultsSource().parse_senate([called], "IA-2026", "IA")
    assert result.snapshot.is_called
    assert result.snapshot.called_party is Party.DEM


@pytest.mark.unit
def test_decode_body_inflates_gzip() -> None:
    """Clarity serves summary.json gzip-encoded; decode_body must inflate it."""
    import gzip

    payload = '[{"SUBCAT": "United States Senate"}]'
    gzipped = gzip.compress(payload.encode("utf-8"))
    # Honored via the Content-Encoding header...
    assert decode_body(gzipped, "gzip") == payload
    # ...and sniffed from the magic bytes even without the header.
    assert decode_body(gzipped, None) == payload
    # Plain bodies pass through unchanged.
    assert decode_body(payload.encode("utf-8"), None) == payload
