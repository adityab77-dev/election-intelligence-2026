"""Unit tests for the CLI command surface (Phase 1).

Phase 1 only guarantees the command surface exists and behaves predictably; the
forecasting subcommands are registered stubs.
"""

from __future__ import annotations

import pytest

from election_intelligence.cli import EXIT_NOT_IMPLEMENTED, build_parser, main


@pytest.mark.unit
def test_no_command_prints_help_and_succeeds() -> None:
    assert main([]) == 0


@pytest.mark.unit
def test_info_command_succeeds() -> None:
    assert main(["info"]) == 0


@pytest.mark.unit
@pytest.mark.parametrize("command", ["run", "backtest", "replay"])
def test_stub_commands_report_not_implemented(command: str) -> None:
    assert main([command]) == EXIT_NOT_IMPLEMENTED


@pytest.mark.unit
def test_parser_registers_all_commands() -> None:
    parser = build_parser()
    # Smoke: parsing each known command resolves a handler.
    for command in ("info", "run", "backtest", "replay"):
        args = parser.parse_args([command])
        assert callable(args.func)
