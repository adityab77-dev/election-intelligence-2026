"""Centralised logging configuration.

A single :func:`configure_logging` call sets up the root logger for the whole
application. It is driven by :class:`~election_intelligence.config.settings.LoggingSettings`
so behaviour (level, JSON vs. plain text, file output) is controlled from the
same place as the rest of the configuration.

Usage at an application entry point (CLI, Streamlit app, test session)::

    from election_intelligence.utils import configure_logging
    configure_logging()

Then, in any module::

    from election_intelligence.utils import get_logger
    logger = get_logger(__name__)
    logger.info("starting ingestion", extra={"source": "polls"})

Configuration is idempotent: calling :func:`configure_logging` more than once
replaces the handlers rather than stacking duplicates.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Any

from election_intelligence.config import get_settings
from election_intelligence.config.settings import LoggingSettings

_CONFIGURED = False

# Attributes present on every LogRecord; anything else was passed via `extra`
# and is worth surfacing in structured output.
_RESERVED_RECORD_KEYS = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
) | {"message", "asctime"}

PLAIN_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects.

    Any keyword passed through the ``extra=`` argument of a logging call is
    merged into the emitted object, which keeps structured context queryable
    in log aggregators.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


def _build_formatter(settings: LoggingSettings) -> logging.Formatter:
    if settings.json_format:
        return JsonFormatter()
    return logging.Formatter(fmt=PLAIN_FORMAT, datefmt=DATE_FORMAT)


def configure_logging(
    settings: LoggingSettings | None = None,
    *,
    force: bool = False,
) -> None:
    """Configure the root logger for the application.

    Args:
        settings: Logging settings to apply. Defaults to the values from
            :func:`election_intelligence.config.get_settings`.
        force: Re-run configuration even if it has already been applied.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    settings = settings or get_settings().logging
    formatter = _build_formatter(settings)

    root = logging.getLogger()
    root.setLevel(settings.level.value)

    # Replace any previously attached handlers so repeat calls stay idempotent.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if settings.log_to_file:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=settings.log_dir / "election_intelligence.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger, configuring logging on first use if needed.

    Args:
        name: Logger name, conventionally ``__name__`` of the calling module.
    """
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
