"""Unit tests for the Phase 1 feed and alert settings groups."""

from __future__ import annotations

import pytest

from election_intelligence.config import get_settings, reset_settings


@pytest.mark.unit
def test_feed_defaults_to_manual() -> None:
    feed = get_settings().feed
    assert feed.provider == "manual"
    assert feed.api_key is None  # env-only; absent by default


@pytest.mark.unit
def test_alerts_enabled_by_default() -> None:
    alerts = get_settings().alerts
    assert alerts.enabled is True
    assert alerts.slack_webhook_url is None


@pytest.mark.unit
def test_feed_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EI_FEED__PROVIDER", "ap")
    monkeypatch.setenv("EI_FEED__API_KEY", "secret-token")
    reset_settings()
    feed = get_settings().feed
    assert feed.provider == "ap"
    # SecretStr must not expose its value via repr/str.
    assert feed.api_key is not None
    assert feed.api_key.get_secret_value() == "secret-token"
    assert "secret-token" not in repr(feed.api_key)
