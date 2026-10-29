"""Configuration management for election-intelligence-2026.

Settings are loaded once and cached. Import the accessor rather than the
settings object directly so that configuration is resolved lazily at first use
(and can be reset in tests):

    from election_intelligence.config import get_settings

    settings = get_settings()
    db_path = settings.database.path
"""

from __future__ import annotations

from election_intelligence.config.settings import (
    AppSettings,
    get_settings,
    reset_settings,
)

__all__ = ["AppSettings", "get_settings", "reset_settings"]
