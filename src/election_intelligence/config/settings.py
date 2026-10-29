"""Typed, layered application settings.

Configuration precedence (highest wins):

    1. Environment variables (prefixed ``EI_``, nested with ``__``)
    2. A local ``.env`` file
    3. Field defaults defined here

Nested groups use a double-underscore delimiter, e.g. ``EI_DATABASE__PATH``
sets :attr:`DatabaseSettings.path`. Secrets (such as the Claude API key) are
*only* read from the environment and never written to disk.

The settings object is cached via :func:`get_settings`; call
:func:`reset_settings` to clear the cache (primarily useful in tests).
"""

from __future__ import annotations

import functools
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: src/election_intelligence/config/settings.py -> up 4 levels.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Environment(str, Enum):
    """Deployment environment the application is running in."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Supported logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseSettings(BaseModel):
    """DuckDB connection settings."""

    path: Path = Field(
        default=PROJECT_ROOT / "data" / "processed" / "election_intelligence.duckdb",
        description="Filesystem path to the DuckDB database file.",
    )
    read_only: bool = Field(
        default=False,
        description="Open the database in read-only mode.",
    )
    threads: int = Field(
        default=4,
        ge=1,
        description="Number of threads DuckDB may use.",
    )


class LoggingSettings(BaseModel):
    """Logging configuration knobs consumed by ``utils.logging_config``."""

    level: LogLevel = Field(default=LogLevel.INFO)
    json_format: bool = Field(
        default=False,
        description="Emit structured JSON logs instead of human-readable lines.",
    )
    log_to_file: bool = Field(default=True)
    log_dir: Path = Field(default=PROJECT_ROOT / "logs")


class ClaudeSettings(BaseModel):
    """Claude API client settings.

    The API key is intentionally a :class:`SecretStr` and has no default; it
    must be supplied via ``EI_CLAUDE__API_KEY`` (or the ``.env`` file).
    """

    api_key: SecretStr | None = Field(default=None)
    model: str = Field(default="claude-opus-4-8")
    max_tokens: int = Field(default=4096, ge=1)
    timeout_seconds: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=3, ge=0)


class AppSettings(BaseSettings):
    """Root application settings object.

    Groups are nested models; override individual fields from the environment
    with the ``EI_<GROUP>__<FIELD>`` convention.
    """

    model_config = SettingsConfigDict(
        env_prefix="EI_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)

    project_root: Path = Field(default=PROJECT_ROOT)
    data_dir: Path = Field(default=PROJECT_ROOT / "data")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    claude: ClaudeSettings = Field(default_factory=ClaudeSettings)

    @field_validator("project_root", "data_dir")
    @classmethod
    def _resolve_path(cls, value: Path) -> Path:
        """Normalise configured paths to absolute form."""
        return value.expanduser().resolve()

    @property
    def is_production(self) -> bool:
        """True when running in the production environment."""
        return self.environment is Environment.PRODUCTION


@functools.lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the cached application settings, loading them on first call."""
    return AppSettings()


def reset_settings() -> None:
    """Clear the cached settings so the next :func:`get_settings` reloads them."""
    get_settings.cache_clear()
