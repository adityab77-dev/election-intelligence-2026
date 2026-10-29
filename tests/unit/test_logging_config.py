"""Unit tests for logging configuration."""

from __future__ import annotations

import json
import logging

import pytest

from election_intelligence.utils.logging_config import (
    JsonFormatter,
    configure_logging,
    get_logger,
)


@pytest.mark.unit
def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("example")
    assert logger.name == "example"


@pytest.mark.unit
def test_configure_logging_is_idempotent() -> None:
    configure_logging(force=True)
    root = logging.getLogger()
    handler_count = len(root.handlers)
    configure_logging()  # no force -> should not add handlers
    assert len(root.handlers) == handler_count


@pytest.mark.unit
def test_json_formatter_includes_extra_fields() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.source = "polls"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["source"] == "polls"
