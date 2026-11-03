"""Wikipedia MediaWiki poll source (Phase A, V1 primary).

Fetches each battleground race's Wikipedia article via the MediaWiki ``parse``
API, extracts the **general-election** opinion-polling table (the current
Democrat-vs-Republican matchup), and normalizes each row into a ``Poll``.

Table selection logic (validated against the real article structure):
- A candidate poll table has a ``Poll source`` + ``Date(s) administered`` +
  ``Sample size`` column and exactly one ``(D)`` and one ``(R)`` candidate
  column. This excludes poll-*aggregation* tables (``Source of poll
  aggregation``) and party-*primary* tables (all same-party candidates).
- Among qualifying tables, the one whose newest poll is most recent is the
  current nominee matchup (older tables are superseded hypotheticals).

No forecasting logic; the resulting ``Poll`` objects go to the existing
``PollIngestor``. Attribution: data derived from Wikipedia (CC-BY-SA).
"""

from __future__ import annotations

import io
import json
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass

import pandas as pd

from election_intelligence.data.ingestion.normalization import (
    clean_pollster,
    parse_date_range,
    parse_pct,
    parse_sample,
)
from election_intelligence.data.ingestion.party_mapping import party_from_header
from election_intelligence.data.ingestion.polls import deterministic_poll_id
from election_intelligence.data.ingestion.pollster_grades import grade_for
from election_intelligence.data.ingestion.sources.base import PollSource
from election_intelligence.data.storage.entities import Party, Poll
from election_intelligence.exceptions import IngestionError
from election_intelligence.utils import get_logger

logger = get_logger(__name__)

_API = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "election-intelligence-2026/0.1 (poll ingestion; contact adityabotta87@gmail.com)"


@dataclass(frozen=True)
class WikiRace:
    race_id: str
    state_code: str
    article: str


# The 8 MVP battlegrounds and their Wikipedia articles.
WIKIPEDIA_RACES: tuple[WikiRace, ...] = (
    WikiRace("GA-2026", "GA", "2026 United States Senate election in Georgia"),
    WikiRace("NC-2026", "NC", "2026 United States Senate election in North Carolina"),
    WikiRace("ME-2026", "ME", "2026 United States Senate election in Maine"),
    WikiRace("MI-2026", "MI", "2026 United States Senate election in Michigan"),
    WikiRace("NH-2026", "NH", "2026 United States Senate election in New Hampshire"),
    WikiRace("TX-2026", "TX", "2026 United States Senate election in Texas"),
    WikiRace("OH-2026-S", "OH", "2026 United States Senate special election in Ohio"),
    WikiRace("IA-2026", "IA", "2026 United States Senate election in Iowa"),
)


def _is_poll_table(columns: list[str]) -> bool:
    lowered = [c.lower() for c in columns]
    has_source = any(c.startswith("poll source") for c in lowered)
    has_dates = any("administered" in c for c in lowered)
    has_sample = any("sample size" in c for c in lowered)
    return has_source and has_dates and has_sample


def _find_column(columns: list[str], *needles: str) -> str | None:
    for col in columns:
        low = col.lower()
        if all(n in low for n in needles):
            return col
    return None


def _party_columns(columns: list[str]) -> tuple[str | None, str | None]:
    dem = [c for c in columns if party_from_header(c) is Party.DEM]
    rep = [c for c in columns if party_from_header(c) is Party.REP]
    # A clean two-way matchup has exactly one Democrat and one Republican column.
    dem_col = dem[0] if len(dem) == 1 else None
    rep_col = rep[0] if len(rep) == 1 else None
    return dem_col, rep_col


def _columns_as_str(frame: pd.DataFrame) -> list[str]:
    return [
        " ".join(str(part) for part in col) if isinstance(col, tuple) else str(col)
        for col in frame.columns
    ]


class WikipediaPollSource(PollSource):
    """Fetches real battleground polls from Wikipedia MediaWiki articles."""

    name = "wikipedia"

    def __init__(
        self,
        races: tuple[WikiRace, ...] = WIKIPEDIA_RACES,
        *,
        timeout: float = 30.0,
    ) -> None:
        self._races = races
        self._timeout = timeout

    # -- live fetch ------------------------------------------------------------
    def _fetch_html(self, article: str) -> str:
        params = urllib.parse.urlencode(
            {
                "action": "parse",
                "page": article,
                "prop": "text",
                "format": "json",
                "formatversion": "2",
            }
        )
        request = urllib.request.Request(
            f"{_API}?{params}", headers={"User-Agent": _USER_AGENT}
        )
        context = ssl.create_default_context()  # honours SSL_CERT_FILE if set
        try:
            with urllib.request.urlopen(request, timeout=self._timeout, context=context) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise IngestionError(f"failed to fetch Wikipedia article {article!r}") from exc
        if "error" in payload:
            raise IngestionError(f"Wikipedia article not found: {article!r}")
        return str(payload["parse"]["text"])

    def fetch(self) -> list[Poll]:
        polls: list[Poll] = []
        for race in self._races:
            try:
                html = self._fetch_html(race.article)
                race_polls = self.parse_race(html, race.race_id, race.state_code)
                logger.info("wikipedia: %s -> %d poll(s)", race.race_id, len(race_polls))
                polls.extend(race_polls)
            except IngestionError as exc:
                logger.warning("wikipedia: skipping %s (%s)", race.race_id, exc)
        return polls

    # -- parsing (pure; unit-testable with a saved HTML fixture) --------------
    def parse_race(self, html: str, race_id: str, state_code: str) -> list[Poll]:
        try:
            tables = pd.read_html(io.StringIO(html), flavor="lxml")
        except ValueError:
            return []  # no tables on the page

        best: list[Poll] = []
        best_latest = None
        for frame in tables:
            columns = _columns_as_str(frame)
            if not _is_poll_table(columns):
                continue
            dem_col, rep_col = _party_columns(columns)
            if dem_col is None or rep_col is None:
                continue  # primary table or ambiguous matchup
            parsed = self._parse_table(frame, columns, dem_col, rep_col, race_id, state_code)
            if not parsed:
                continue
            latest = max(poll.field_end for poll in parsed)
            if best_latest is None or latest > best_latest:
                best, best_latest = parsed, latest
        return best

    def _parse_table(
        self,
        frame: pd.DataFrame,
        columns: list[str],
        dem_col: str,
        rep_col: str,
        race_id: str,
        state_code: str,
    ) -> list[Poll]:
        source_col = _find_column(columns, "poll source")
        date_col = _find_column(columns, "administered")
        sample_col = _find_column(columns, "sample size")
        if not (source_col and date_col):
            return []

        renamed = frame.copy()
        renamed.columns = columns
        polls: list[Poll] = []
        for _, row in renamed.iterrows():
            pollster = clean_pollster(row[source_col])
            if not pollster or "average" in pollster.lower():
                continue
            _start, end = parse_date_range(str(row[date_col]))
            if end is None:
                continue
            dem_pct = parse_pct(row[dem_col])
            rep_pct = parse_pct(row[rep_col])
            if dem_pct is None or rep_pct is None:
                continue
            size, population = parse_sample(row[sample_col]) if sample_col else (None, None)
            poll = Poll(
                race_id=race_id,
                pollster=pollster,
                pollster_grade=grade_for(pollster),
                field_start=_start,
                field_end=end,
                sample_size=size,
                population=population,
                margin_dem_minus_rep=dem_pct - rep_pct,
                url=None,
            )
            poll.poll_id = deterministic_poll_id(poll)  # dedup across refreshes
            polls.append(poll)
        return polls


__all__ = ["WikipediaPollSource", "WikiRace", "WIKIPEDIA_RACES"]
