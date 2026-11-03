"""Integration tests for the Wikipedia poll source (parsing + ingestion).

Uses a committed HTML fixture of the real 2026 Georgia Senate article, so the
parser is tested against the real table structure without hitting the network.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

pytest.importorskip("lxml")
pytest.importorskip("duckdb")

from election_intelligence.data.ingestion.polls import PollIngestor  # noqa: E402
from election_intelligence.data.ingestion.sources.wikipedia import (  # noqa: E402
    WikiRace,
    WikipediaPollSource,
)
from election_intelligence.data.storage import Database, SeedLoader  # noqa: E402
from tests.fixtures import FIXTURES_DIR  # noqa: E402

GA_FIXTURE = FIXTURES_DIR / "wikipedia" / "ga_2026_senate.html"


def _ga_html() -> str:
    return GA_FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database()
    database.migrate()
    SeedLoader(database).load_all()
    yield database
    database.close()


@pytest.mark.integration
def test_parse_race_extracts_general_election_polls() -> None:
    polls = WikipediaPollSource().parse_race(_ga_html(), "GA-2026", "GA")
    assert len(polls) >= 10
    assert all(p.race_id == "GA-2026" for p in polls)
    # The selected table is the current nominee matchup -> newest poll is recent.
    assert max(p.field_end for p in polls) == date(2026, 11, 2)
    assert all(-100.0 <= p.margin_dem_minus_rep <= 100.0 for p in polls)
    # Grades were attached for known pollsters.
    assert any(p.pollster_grade is not None for p in polls)


@pytest.mark.integration
def test_parse_race_is_deterministic() -> None:
    a = WikipediaPollSource().parse_race(_ga_html(), "GA-2026", "GA")
    b = WikipediaPollSource().parse_race(_ga_html(), "GA-2026", "GA")
    assert {p.poll_id for p in a} == {p.poll_id for p in b}


@pytest.mark.integration
def test_ingest_wikipedia_polls_into_table(db: Database) -> None:
    polls = WikipediaPollSource().parse_race(_ga_html(), "GA-2026", "GA")
    unique_ids = {p.poll_id for p in polls}
    report = PollIngestor(db).ingest(polls)
    assert report.ingested == len(polls)
    assert report.rejected == 0
    # Dedup: polls sharing a natural key collapse to one stored row.
    assert len(db.polls.list_by_race("GA-2026")) == len(unique_ids)
    assert db.polls.count() == len(unique_ids)


@pytest.mark.integration
def test_ingestion_is_idempotent(db: Database) -> None:
    polls = WikipediaPollSource().parse_race(_ga_html(), "GA-2026", "GA")
    ingestor = PollIngestor(db)
    ingestor.ingest(polls)
    count = db.polls.count()
    ingestor.ingest(WikipediaPollSource().parse_race(_ga_html(), "GA-2026", "GA"))
    assert db.polls.count() == count  # deterministic ids -> upsert


@pytest.mark.integration
def test_fetch_uses_parser_without_network() -> None:
    # Subclass that returns the fixture instead of calling Wikipedia.
    class _OfflineSource(WikipediaPollSource):
        def _fetch_html(self, article: str) -> str:
            return _ga_html()

    source = _OfflineSource(races=(WikiRace("GA-2026", "GA", "fixture"),))
    polls = source.fetch()
    assert len(polls) >= 10
    assert all(p.race_id == "GA-2026" for p in polls)
