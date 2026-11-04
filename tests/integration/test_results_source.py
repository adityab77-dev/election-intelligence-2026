"""Integration tests for the Wikipedia results source and live update."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

pytest.importorskip("lxml")
pytest.importorskip("duckdb")
pytest.importorskip("numpy")

from election_intelligence.data.ingestion.polls import (  # noqa: E402
    BATTLEGROUND_RACES,
    PollIngestor,
)
from election_intelligence.data.ingestion.results import (  # noqa: E402
    ResultsIngestor,
    WikipediaResultsSource,
)
from election_intelligence.data.ingestion.sources.wikipedia import WikiRace  # noqa: E402
from election_intelligence.data.storage import Database, SeedLoader  # noqa: E402
from election_intelligence.data.storage.entities import Party  # noqa: E402
from election_intelligence.forecast import ForecastEngine  # noqa: E402
from election_intelligence.live import run_live_update  # noqa: E402

GENERAL_HTML = """
<table class="wikitable"><tr><th>Party</th><th>Party</th><th>Candidate</th><th>Votes</th><th>%</th></tr>
<tr><td>x</td><td>Democratic</td><td>Jon Ossoff (incumbent)</td><td>1,920,000</td><td>52.0</td></tr>
<tr><td>x</td><td>Republican</td><td>Mike Collins</td><td>1,700,000</td><td>46.1</td></tr>
<tr><td>Total votes</td><td>Total votes</td><td>Total votes</td><td>3,620,000</td><td>100.0</td></tr></table>
"""
PRIMARY_HTML = """
<table class="wikitable"><tr><th>Party</th><th>Party</th><th>Candidate</th><th>Votes</th><th>%</th></tr>
<tr><td>x</td><td>Republican</td><td>Mike Collins</td><td>390,000</td><td>55.5</td></tr>
<tr><td>x</td><td>Republican</td><td>Derek Dooley</td><td>312,000</td><td>44.5</td></tr></table>
"""


class _OfflineResults(WikipediaResultsSource):
    def __init__(self, html: str) -> None:
        super().__init__(races=(WikiRace("GA-2026", "GA", "fixture"),))
        self._html = html

    def _fetch_html(self, article: str) -> str:
        return self._html


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database()
    database.migrate()
    SeedLoader(database).load_all()
    PollIngestor(database).ingest_file()
    engine = ForecastEngine()
    for code, race_id in BATTLEGROUND_RACES.items():
        engine.persist(
            database,
            engine.forecast_race(database, race_id, state_code=code, forecast_date=date(2026, 11, 3)),
        )
    yield database
    database.close()


@pytest.mark.integration
def test_parse_general_results() -> None:
    parsed = WikipediaResultsSource().parse_race(GENERAL_HTML, "GA-2026", "GA")
    assert parsed is not None
    snap = parsed.snapshot
    assert snap.dem_votes == 1_920_000 and snap.rep_votes == 1_700_000
    assert snap.leader_party is Party.DEM
    assert snap.margin == pytest.approx((1_920_000 - 1_700_000) / 3_620_000 * 100, abs=0.1)
    assert 0 < snap.percent_reporting <= 100
    assert len(parsed.candidates) == 2


@pytest.mark.integration
def test_primary_table_is_ignored() -> None:
    # Single-party (primary) table -> not a general-election matchup -> None.
    assert WikipediaResultsSource().parse_race(PRIMARY_HTML, "GA-2026", "GA") is None


@pytest.mark.integration
def test_ingest_stores_snapshot_and_results(db: Database) -> None:
    report = ResultsIngestor(db).ingest_source(_OfflineResults(GENERAL_HTML))
    assert report.snapshots == 1
    assert report.results == 2
    snap = db.reporting_snapshots.latest_for_race("GA-2026")
    assert snap is not None and snap.dem_votes == 1_920_000


@pytest.mark.integration
def test_live_update_produces_live_run_and_shifts_ga(db: Database) -> None:
    ga_poll = db.state_forecasts.latest_for_race("GA-2026").mean_margin
    ResultsIngestor(db).ingest_source(_OfflineResults(GENERAL_HTML))
    output = run_live_update(db, seed=2026, n_simulations=20_000)
    assert output is not None
    run = db.simulation_runs.latest()
    assert run.regime.value == "live"
    # GA's counted margin (+6) is more Democratic than its poll margin, so the
    # blended GA forecast moves Democratic relative to the poll-only baseline.
    assert ga_poll < 6.1  # sanity: poll was less D than the counted result
