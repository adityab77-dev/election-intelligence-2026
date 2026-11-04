"""Wikipedia election-results source (Phase E).

Parses the **general-election results table** from each battleground's Wikipedia
article (the ``{{Election box}}`` tables: Party / Candidate / Votes / %) and
normalises it into a ``ReportingSnapshot`` + per-candidate ``ElectionResult``s.

Table selection: a results table qualifies as the general election when it has
both a Democratic and a Republican candidate *with votes*; among those the one
with the most total votes is the live general result (primaries/runoffs are
single-party and excluded; an empty skeleton table has 0 votes and is ignored).

**Percent reporting:** Wikipedia result tables carry no live reporting figure, so
it is *estimated* as `counted_total / expected_turnout` (a documented proxy, not
an official number). No forecasting logic here.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from election_intelligence.data.ingestion.normalization import parse_pct
from election_intelligence.data.ingestion.results.base import RaceResults, ResultsSource
from election_intelligence.data.ingestion.sources.wikipedia import WIKIPEDIA_RACES, WikiRace
from election_intelligence.data.storage.entities import ElectionResult, Party, ReportingSnapshot
from election_intelligence.exceptions import IngestionError
from election_intelligence.utils import get_logger

logger = get_logger(__name__)

_API = "https://en.wikipedia.org/w/api.php"
_UA = "election-intelligence-2026/0.1 (results; adityabotta87@gmail.com)"
_VOTES_RE = re.compile(r"[\d,]{2,}")

# Approximate expected turnout per race, used ONLY to estimate percent reporting
# (Wikipedia provides none). Rough recent-cycle anchors — tune as needed.
EXPECTED_TURNOUT: dict[str, int] = {
    "GA-2026": 4_000_000, "NC-2026": 3_800_000, "ME-2026": 800_000,
    "MI-2026": 4_500_000, "NH-2026": 800_000, "TX-2026": 8_500_000,
    "OH-2026-S": 4_500_000, "IA-2026": 1_250_000,
}


def _party(text: object) -> Party | None:
    t = str(text).lower()
    if "democrat" in t:
        return Party.DEM
    if "republic" in t:
        return Party.REP
    if "independ" in t:
        return Party.IND
    if "libertar" in t:
        return Party.LIB
    if "green" in t:
        return Party.GRN
    return None


def _votes(text: object) -> int | None:
    match = _VOTES_RE.search(str(text).replace("\xa0", ""))
    return int(match.group(0).replace(",", "")) if match else None


def _columns(frame: pd.DataFrame) -> list[str]:
    return [
        " ".join(str(p) for p in c) if isinstance(c, tuple) else str(c)
        for c in frame.columns
    ]


def _snapshot_id(race_id: str, reported_at: datetime) -> str:
    key = f"{race_id}|wikipedia|{reported_at.isoformat()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


class WikipediaResultsSource(ResultsSource):
    """Fetches real battleground results from Wikipedia article result tables."""

    name = "wikipedia"

    def __init__(
        self, races: tuple[WikiRace, ...] = WIKIPEDIA_RACES, *, timeout: float = 30.0
    ) -> None:
        self._races = races
        self._timeout = timeout

    def _fetch_html(self, article: str) -> str:
        params = urllib.parse.urlencode(
            {"action": "parse", "page": article, "prop": "text",
             "format": "json", "formatversion": "2"}
        )
        request = urllib.request.Request(
            f"{_API}?{params}", headers={"User-Agent": _UA}
        )
        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout, context=context) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise IngestionError(f"failed to fetch {article!r}") from exc
        if "error" in payload:
            raise IngestionError(f"Wikipedia article not found: {article!r}")
        return str(payload["parse"]["text"])

    def fetch(self) -> list[RaceResults]:
        out: list[RaceResults] = []
        for race in self._races:
            try:
                parsed = self.parse_race(
                    self._fetch_html(race.article), race.race_id, race.state_code
                )
            except IngestionError as exc:
                logger.warning("results: skipping %s (%s)", race.race_id, exc)
                continue
            if parsed is None:
                logger.info("results: %s -> no results reported yet", race.race_id)
                continue
            logger.info(
                "results: %s -> %.0f%% reporting, %d votes",
                race.race_id, parsed.snapshot.percent_reporting, parsed.snapshot.total_votes,
            )
            out.append(parsed)
        return out

    # -- parsing (pure; testable with a saved/constructed fixture) ------------
    def parse_race(self, html: str, race_id: str, state_code: str) -> RaceResults | None:
        try:
            tables = pd.read_html(io.StringIO(html), flavor="lxml")
        except ValueError:
            return None
        best: RaceResults | None = None
        best_total = 0
        for frame in tables:
            columns = _columns(frame)
            lowered = [c.lower() for c in columns]
            if not (any(c == "votes" for c in lowered) and any(c == "candidate" for c in lowered)):
                continue
            parsed = self._parse_table(frame, columns, race_id, state_code)
            if parsed is None:
                continue
            snap = parsed.snapshot
            # General election = both parties present with votes.
            if snap.dem_votes > 0 and snap.rep_votes > 0 and snap.total_votes > best_total:
                best, best_total = parsed, snap.total_votes
        return best

    def _parse_table(
        self, frame: pd.DataFrame, columns: list[str], race_id: str, state_code: str
    ) -> RaceResults | None:
        working = frame.copy()
        working.columns = columns
        lookup = {c.lower(): c for c in columns}
        cand_col = lookup.get("candidate")
        votes_col = lookup.get("votes")
        share_col = lookup.get("%")
        party_col = None
        for col in columns:
            sample = " ".join(str(v) for v in working[col].tolist()[:6]).lower()
            if "democrat" in sample or "republic" in sample:
                party_col = col
                break
        if not (cand_col and votes_col and party_col):
            return None

        reported_at = datetime.now(timezone.utc)
        dem = rep = other = 0
        candidates: list[ElectionResult] = []
        for _, row in working.iterrows():
            name = str(row[cand_col]).strip()
            if not name or "total" in name.lower():
                continue
            votes = _votes(row[votes_col])
            if votes is None:
                continue
            party = _party(row[party_col])
            share = parse_pct(row[share_col]) if share_col else None
            if party is Party.DEM:
                dem += votes
            elif party is Party.REP:
                rep += votes
            else:
                other += votes
            candidates.append(
                ElectionResult(
                    race_id=race_id,
                    state_code=state_code,
                    candidate_name=re.sub(r"\(.*?\)", "", name).strip(),
                    party=party,
                    votes=votes,
                    vote_share=share,
                    source="wikipedia",
                    reported_at=reported_at,
                )
            )

        total = dem + rep + other
        if total <= 0:
            return None
        expected = EXPECTED_TURNOUT.get(race_id, 1_000_000)
        percent_reporting = min(100.0, total / expected * 100.0)
        margin = (dem - rep) / total * 100.0
        leader = Party.DEM if dem >= rep else Party.REP
        called = percent_reporting >= 99.0
        for candidate in candidates:
            candidate.percent_reporting = percent_reporting
            candidate.is_called = called

        snapshot = ReportingSnapshot(
            snapshot_id=_snapshot_id(race_id, reported_at),
            race_id=race_id,
            source="wikipedia",
            reported_at=reported_at,
            percent_reporting=percent_reporting,
            total_votes=total,
            dem_votes=dem,
            rep_votes=rep,
            other_votes=other,
            margin=margin,
            leader_party=leader,
            is_called=called,
            called_party=leader if called else None,
        )
        return RaceResults(snapshot=snapshot, candidates=candidates)


__all__ = ["WikipediaResultsSource", "EXPECTED_TURNOUT"]
