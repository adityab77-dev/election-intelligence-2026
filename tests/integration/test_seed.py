"""Integration tests for the seed-data framework."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("duckdb")

from election_intelligence.data.storage import Database, SeedLoader  # noqa: E402
from election_intelligence.data.storage.entities import CountingRule  # noqa: E402


@pytest.fixture
def db() -> Iterator[Database]:
    database = Database()
    database.migrate()
    yield database
    database.close()


@pytest.mark.integration
def test_seed_loads_states_and_races(db: Database) -> None:
    summary = SeedLoader(db).load_all()
    assert summary["states"] == 51  # 50 states + DC
    assert summary["senate_races"] >= 10
    assert db.states.count() == 51
    assert db.senate_races.count() >= 10


@pytest.mark.integration
def test_seed_is_idempotent(db: Database) -> None:
    loader = SeedLoader(db)
    loader.load_all()
    first = db.states.count()
    loader.load_all()
    assert db.states.count() == first  # upsert, not duplicate


@pytest.mark.integration
def test_seed_preserves_counting_rules(db: Database) -> None:
    SeedLoader(db).load_all()
    assert db.senate_races.get("GA-2026").counting_rule is CountingRule.MAJORITY_RUNOFF
    assert db.senate_races.get("ME-2026").counting_rule is CountingRule.RANKED_CHOICE
    assert db.senate_races.get("FL-2026-S").is_special is True
