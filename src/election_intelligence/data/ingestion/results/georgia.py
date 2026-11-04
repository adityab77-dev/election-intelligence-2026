"""Georgia election-results source (Phase E) — official SoS "Enhanced Voting" feed.

Georgia publishes official results as JSON at
``results.sos.ga.gov/results/public/api/elections/Georgia/General11032026/data``
(the same "Enhanced Voting" platform several states use). The payload is a dict
with ``ballotItems`` (contests); each contest has ``summaryResults.ballotOptions``
(candidates: ``name``, ``voteCount``, ``party``, ``isWinner``) and a
``reportingStatus`` (``reportingUnits`` / ``totalUnits``).

Official public-record data — free, machine-readable, legally reusable. Returns
nothing until Georgia publishes results (the endpoint 204s when empty). No
forecasting logic; emits the same ``RaceResults`` as the other sources.
"""

from __future__ import annotations

import json
import ssl
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from election_intelligence.data.ingestion.results.base import RaceResults, ResultsSource
from election_intelligence.data.ingestion.results.wikipedia import _party, _snapshot_id
from election_intelligence.data.storage.entities import ElectionResult, Party, ReportingSnapshot
from election_intelligence.exceptions import IngestionError
from election_intelligence.utils import get_logger

logger = get_logger(__name__)

_UA = "election-intelligence-2026/0.1 (results; adityabotta87@gmail.com)"
GEORGIA_RACE_IDS: frozenset[str] = frozenset({"GA-2026"})


@dataclass(frozen=True)
class EnhancedVotingRace:
    race_id: str
    state_code: str
    base_url: str
    jurisdiction: str
    election: str


GEORGIA = EnhancedVotingRace(
    race_id="GA-2026", state_code="GA",
    base_url="https://results.sos.ga.gov", jurisdiction="Georgia",
    election="General11032026",
)


def _en(field: object) -> str:
    """Extract the English text from a localized ``[{languageId, text}]`` field."""
    if isinstance(field, list):
        for item in field:
            if isinstance(item, dict) and item.get("languageId") == "en":
                return str(item.get("text", ""))
        if field and isinstance(field[0], dict):
            return str(field[0].get("text", ""))
    return str(field) if field is not None else ""


def _is_us_senate(name: str) -> bool:
    low = name.lower()
    return "senat" in low and ("u.s." in low or "united states" in low) and "state senate" not in low


class GeorgiaResultsSource(ResultsSource):
    """Fetches official U.S. Senate results from Georgia's Enhanced Voting feed."""

    name = "georgia-sos"

    def __init__(self, race: EnhancedVotingRace = GEORGIA, *, timeout: float = 30.0) -> None:
        self._race = race
        self._timeout = timeout

    def _fetch_data(self) -> dict | None:
        url = (
            f"{self._race.base_url}/results/public/api/elections/"
            f"{self._race.jurisdiction}/{self._race.election}/data"
        )
        request = urllib.request.Request(url, headers={"User-Agent": _UA})
        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout, context=context) as resp:
                body = resp.read().decode("utf-8")
        except OSError as exc:
            raise IngestionError(f"failed to fetch {url}") from exc
        if not body.strip():  # HTTP 204 / empty -> no results published yet
            return None
        return json.loads(body)

    def fetch(self) -> list[RaceResults]:
        try:
            data = self._fetch_data()
        except (IngestionError, ValueError) as exc:
            logger.warning("georgia: skipping (%s)", exc)
            return []
        if data is None:
            logger.info("georgia: no results published yet")
            return []
        parsed = self.parse(data, self._race.race_id, self._race.state_code)
        if parsed is None:
            return []
        logger.info(
            "georgia: %s -> %.0f%% reporting, %d votes",
            parsed.snapshot.race_id, parsed.snapshot.percent_reporting, parsed.snapshot.total_votes,
        )
        return [parsed]

    # -- parsing (pure; testable with a saved/constructed payload) -----------
    def parse(self, data: dict, race_id: str, state_code: str) -> RaceResults | None:
        contest = None
        for item in data.get("ballotItems", []):
            if _is_us_senate(_en(item.get("name"))):
                contest = item
                break
        if contest is None:
            return None

        options = (contest.get("summaryResults") or {}).get("ballotOptions") or []
        if not options:
            return None

        reported_at = datetime.now(timezone.utc)
        dem = rep = other = 0
        candidates: list[ElectionResult] = []
        called_party: Party | None = None
        for option in options:
            party = _party(_en((option.get("party") or {}).get("name")))
            count = int(option.get("voteCount") or 0)
            if party is Party.DEM:
                dem += count
            elif party is Party.REP:
                rep += count
            else:
                other += count
            if option.get("isWinner"):
                called_party = party
            candidates.append(
                ElectionResult(
                    race_id=race_id, state_code=state_code,
                    candidate_name=_en(option.get("name")), party=party,
                    votes=count, source="georgia-sos", reported_at=reported_at,
                )
            )

        total = int(contest.get("voteTotal") or (dem + rep + other))
        if total <= 0:
            return None
        status = contest.get("reportingStatus") or {}
        total_units = status.get("totalUnits") or 0
        reporting_units = status.get("reportingUnits") or 0
        percent_reporting = (
            min(100.0, reporting_units / total_units * 100.0) if total_units else 0.0
        )
        margin = (dem - rep) / total * 100.0
        leader = Party.DEM if dem >= rep else Party.REP
        is_called = called_party is not None
        for candidate in candidates:
            candidate.percent_reporting = percent_reporting
            candidate.is_called = is_called

        snapshot = ReportingSnapshot(
            snapshot_id=_snapshot_id(race_id, reported_at),
            race_id=race_id, source="georgia-sos", reported_at=reported_at,
            percent_reporting=percent_reporting, total_votes=total,
            dem_votes=dem, rep_votes=rep, other_votes=other, margin=margin,
            leader_party=leader, is_called=is_called,
            called_party=called_party or (leader if is_called else None),
        )
        return RaceResults(snapshot=snapshot, candidates=candidates)


__all__ = ["GeorgiaResultsSource", "EnhancedVotingRace", "GEORGIA", "GEORGIA_RACE_IDS"]
