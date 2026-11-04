"""Clarity/Scytl election-results source (Phase E, primary).

Pulls official election-night results from the Clarity platform's JSON feed,
which many states publish at a predictable path:

    {base}/{ST}/{election_id}/current_ver.txt          -> current version
    {base}/{ST}/{election_id}/{ver}/json/en/summary.json

The summary is a list of contest records; the US Senate contest exposes parallel
arrays ``CH`` (candidates), ``P`` (parties), ``V`` (votes), ``PCT`` (percent),
``T`` (total), ``W`` (winner flags), plus ``TP``/``PR`` (reporting units). This is
official public-record data — free, machine-readable, and legally reusable.

Confirmed live for Iowa (``electionresults.iowa.gov/IA/127077``). Additional
Clarity states are added to ``CLARITY_RACES`` as their election IDs are found.
No forecasting logic here; emits the same ``RaceResults`` as the Wikipedia source.
"""

from __future__ import annotations

import gzip
import json
import ssl
import urllib.request
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone

from election_intelligence.data.ingestion.results.base import RaceResults, ResultsSource
from election_intelligence.data.ingestion.results.wikipedia import EXPECTED_TURNOUT, _snapshot_id
from election_intelligence.data.storage.entities import ElectionResult, Party, ReportingSnapshot
from election_intelligence.exceptions import IngestionError
from election_intelligence.utils import get_logger

logger = get_logger(__name__)

_UA = "election-intelligence-2026/0.1 (results; adityabotta87@gmail.com)"
_PARTY_CODES = {
    "DEM": Party.DEM, "REP": Party.REP, "IND": Party.IND,
    "LIB": Party.LIB, "GRN": Party.GRN,
}


@dataclass(frozen=True)
class ClarityRace:
    race_id: str
    state: str          # Clarity state segment, e.g. "IA"
    base_url: str       # e.g. "https://electionresults.iowa.gov"
    election_id: str    # Clarity election id, e.g. "127077"


# Configured Clarity states (election ids discovered via Step E-0.5). The
# version (current_ver.txt) is fetched automatically each refresh.
CLARITY_RACES: tuple[ClarityRace, ...] = (
    ClarityRace("IA-2026", "IA", "https://electionresults.iowa.gov", "127077"),
)
CLARITY_RACE_IDS: frozenset[str] = frozenset(r.race_id for r in CLARITY_RACES)


def _map_party(code: object) -> Party | None:
    return _PARTY_CODES.get(str(code).strip().upper())


def decode_body(raw: bytes, content_encoding: str | None = None) -> str:
    """Decode an HTTP body, transparently inflating gzip/deflate payloads.

    Clarity/Scytl serves ``summary.json`` with ``Content-Encoding: gzip`` (and
    urllib does not auto-decompress). We honor the header and also sniff the
    gzip magic bytes, so a pre-compressed file served without the header still
    decodes. Falls back to the raw bytes if decompression fails.
    """
    enc = (content_encoding or "").lower()
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    elif enc == "deflate":
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw.decode("utf-8")


class ClarityResultsSource(ResultsSource):
    """Fetches official Senate results from state Clarity JSON feeds."""

    name = "clarity"

    def __init__(
        self, races: tuple[ClarityRace, ...] = CLARITY_RACES, *, timeout: float = 30.0
    ) -> None:
        self._races = races
        self._timeout = timeout

    def _get(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": _UA})
        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout, context=context) as resp:
                return decode_body(resp.read(), resp.headers.get("Content-Encoding"))
        except OSError as exc:
            raise IngestionError(f"failed to fetch {url}") from exc

    def _fetch_summary(self, race: ClarityRace) -> list[dict]:
        version = self._get(
            f"{race.base_url}/{race.state}/{race.election_id}/current_ver.txt"
        ).strip()
        body = self._get(
            f"{race.base_url}/{race.state}/{race.election_id}/{version}/json/en/summary.json"
        )
        data = json.loads(body)
        return data if isinstance(data, list) else data.get("Contests", [])

    def fetch(self) -> list[RaceResults]:
        out: list[RaceResults] = []
        for race in self._races:
            try:
                parsed = self.parse_senate(self._fetch_summary(race), race.race_id, race.state)
            except (IngestionError, ValueError) as exc:
                logger.warning("clarity: skipping %s (%s)", race.race_id, exc)
                continue
            if parsed is None:
                logger.info("clarity: %s -> no Senate contest found", race.race_id)
                continue
            logger.info(
                "clarity: %s -> %.0f%% reporting, %d votes",
                race.race_id, parsed.snapshot.percent_reporting, parsed.snapshot.total_votes,
            )
            out.append(parsed)
        return out

    # -- parsing (pure; testable with a saved summary.json) ------------------
    def parse_senate(
        self, contests: list[dict], race_id: str, state_code: str
    ) -> RaceResults | None:
        contest = None
        for item in contests:
            label = f"{item.get('SUBCAT', '')} {item.get('C', '')}".lower()
            if "senate" in label or "senator" in label:
                contest = item
                break
        if contest is None:
            return None

        names = contest.get("CH", [])
        parties = contest.get("P", [])
        votes = contest.get("V", [])
        winners = contest.get("W", [])
        if not (names and votes) or len(names) != len(votes):
            return None

        reported_at = datetime.now(timezone.utc)
        dem = rep = other = 0
        candidates: list[ElectionResult] = []
        called_party: Party | None = None
        for i, name in enumerate(names):
            party = _map_party(parties[i]) if i < len(parties) else None
            count = int(votes[i]) if votes[i] is not None else 0
            if party is Party.DEM:
                dem += count
            elif party is Party.REP:
                rep += count
            else:
                other += count
            if i < len(winners) and winners[i]:
                called_party = party
            candidates.append(
                ElectionResult(
                    race_id=race_id, state_code=state_code, candidate_name=str(name),
                    party=party, votes=count, source="clarity", reported_at=reported_at,
                )
            )

        total_arr = contest.get("T") or []
        total = int(total_arr[0]) if total_arr else (dem + rep + other)
        if total <= 0:
            return None

        total_units = contest.get("TP") or 0
        reporting_units = contest.get("PR") or 0
        if total_units and total_units > 0:
            percent_reporting = min(100.0, reporting_units / total_units * 100.0)
        else:
            expected = EXPECTED_TURNOUT.get(race_id, 1_000_000)
            percent_reporting = min(100.0, total / expected * 100.0)

        margin = (dem - rep) / total * 100.0
        leader = Party.DEM if dem >= rep else Party.REP
        is_called = called_party is not None or percent_reporting >= 99.9
        for candidate in candidates:
            candidate.percent_reporting = percent_reporting
            candidate.is_called = is_called

        snapshot = ReportingSnapshot(
            snapshot_id=_snapshot_id(race_id, reported_at),
            race_id=race_id, source="clarity", reported_at=reported_at,
            percent_reporting=percent_reporting, total_votes=total,
            dem_votes=dem, rep_votes=rep, other_votes=other, margin=margin,
            leader_party=leader, is_called=is_called,
            called_party=called_party or (leader if is_called else None),
        )
        return RaceResults(snapshot=snapshot, candidates=candidates)


__all__ = [
    "ClarityResultsSource", "ClarityRace", "CLARITY_RACES", "CLARITY_RACE_IDS", "decode_body",
]
