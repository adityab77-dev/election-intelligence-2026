"""Unit tests for the Georgia (Enhanced Voting) results parser (no network/DB)."""

from __future__ import annotations

import pytest

pytest.importorskip("pandas")  # results package imports pandas transitively

from election_intelligence.data.ingestion.results import GeorgiaResultsSource  # noqa: E402
from election_intelligence.data.storage.entities import Party  # noqa: E402


def _opt(name: str, votes: int, party: str, winner: bool = False) -> dict:
    return {
        "name": [{"languageId": "en", "text": name}],
        "voteCount": votes,
        "party": {"name": [{"languageId": "en", "text": party}]},
        "isWinner": winner,
    }


def _payload(options: list[dict], contest: str = "United States Senate",
             total: int = 3_620_000, reporting: int = 120, units: int = 159) -> dict:
    return {
        "ballotItems": [
            {"name": [{"languageId": "en", "text": "U.S. House District 1"}],
             "summaryResults": {"ballotOptions": []}},
            {
                "name": [{"languageId": "en", "text": contest}],
                "voteTotal": total,
                "reportingStatus": {"reportingUnits": reporting, "totalUnits": units},
                "summaryResults": {"ballotOptions": options},
            },
        ]
    }


SENATE_OPTS = [
    _opt("Jon Ossoff", 1_920_000, "Democratic"),
    _opt("Mike Collins", 1_700_000, "Republican"),
]


@pytest.mark.unit
def test_parse_us_senate() -> None:
    result = GeorgiaResultsSource().parse(_payload(SENATE_OPTS), "GA-2026", "GA")
    assert result is not None
    snap = result.snapshot
    assert snap.dem_votes == 1_920_000 and snap.rep_votes == 1_700_000
    assert snap.leader_party is Party.DEM
    assert snap.percent_reporting == pytest.approx(120 / 159 * 100, abs=0.1)
    assert len(result.candidates) == 2


@pytest.mark.unit
def test_state_senate_is_not_matched() -> None:
    payload = _payload(SENATE_OPTS, contest="State Senate District 5")
    assert GeorgiaResultsSource().parse(payload, "GA-2026", "GA") is None


@pytest.mark.unit
def test_winner_flag_marks_called() -> None:
    opts = [
        _opt("Jon Ossoff", 1_920_000, "Democratic", winner=True),
        _opt("Mike Collins", 1_700_000, "Republican"),
    ]
    result = GeorgiaResultsSource().parse(_payload(opts), "GA-2026", "GA")
    assert result.snapshot.is_called
    assert result.snapshot.called_party is Party.DEM
