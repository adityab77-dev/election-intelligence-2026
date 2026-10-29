"""Unit tests for the configuration layer.

These double as smoke tests that the scaffold imports cleanly and that the
settings precedence and caching behave as documented.
"""

from __future__ import annotations

import pytest

from election_intelligence.config import get_settings, reset_settings
from election_intelligence.config.settings import Environment


@pytest.mark.unit
def test_settings_load_defaults() -> None:
    settings = get_settings()
    assert settings.environment is Environment.TESTING
    assert settings.database.threads >= 1


@pytest.mark.unit
def test_settings_are_cached() -> None:
    assert get_settings() is get_settings()


@pytest.mark.unit
def test_reset_settings_clears_cache() -> None:
    first = get_settings()
    reset_settings()
    assert get_settings() is not first


@pytest.mark.unit
def test_env_override_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EI_DATABASE__THREADS", "7")
    reset_settings()
    assert get_settings().database.threads == 7
