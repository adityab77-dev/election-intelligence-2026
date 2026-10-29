"""Shared pytest fixtures.

Fixtures here apply to the whole suite. The autouse ``_test_environment``
fixture isolates every test from the developer's real configuration: it clears
the settings cache and points data/logs at a temporary directory so no test
touches the real database or writes stray log files.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from election_intelligence.config import get_settings, reset_settings
from election_intelligence.config.settings import AppSettings


@pytest.fixture(autouse=True)
def _test_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Isolate configuration for each test using a temp directory."""
    monkeypatch.setenv("EI_ENVIRONMENT", "testing")
    monkeypatch.setenv("EI_DATABASE__PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("EI_LOGGING__LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("EI_LOGGING__LOG_TO_FILE", "false")

    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def settings() -> AppSettings:
    """Return freshly-resolved settings for the isolated test environment."""
    return get_settings()
