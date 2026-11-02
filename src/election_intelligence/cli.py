"""Command-line entry point for election-intelligence-2026.

A thin dispatcher wired up as the ``election-intelligence`` console script (see
``pyproject.toml``). Phase 1 provides the command surface and configuration/logging
wiring only; the ``run``, ``backtest`` and ``replay`` subcommands are registered
stubs that will be implemented in their respective phases (see ``BUILD_PLAN.md``).

No forecasting logic lives here.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from election_intelligence import __version__
from election_intelligence.config import get_settings
from election_intelligence.utils import configure_logging, get_logger

logger = get_logger(__name__)

# Exit code used by not-yet-implemented subcommands.
EXIT_NOT_IMPLEMENTED = 2


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser and register subcommands."""
    parser = argparse.ArgumentParser(
        prog="election-intelligence",
        description="Election forecasting and analysis platform.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    info = subparsers.add_parser(
        "info",
        help="Print the resolved runtime configuration.",
    )
    info.set_defaults(func=_cmd_info)

    run = subparsers.add_parser(
        "run",
        help="Run one model tick (worker pipeline). [Phase 5-9]",
    )
    run.set_defaults(func=_stub("run", "Phase 5-9 — forecast/live pipeline"))

    backtest = subparsers.add_parser(
        "backtest",
        help="Run the offline calibration backtest. [Phase 8]",
    )
    backtest.set_defaults(func=_stub("backtest", "Phase 8 — calibration framework"))

    replay = subparsers.add_parser(
        "replay",
        help="Replay an archived election night. [Phase 7]",
    )
    replay.set_defaults(func=_stub("replay", "Phase 7 — historical replay framework"))

    return parser


def _cmd_info(_: argparse.Namespace) -> int:
    """Report the active environment and key configuration paths."""
    settings = get_settings()
    logger.info("environment=%s", settings.environment.value)
    logger.info("database=%s", settings.database.path)
    logger.info("log_dir=%s", settings.logging.log_dir)
    logger.info("feed_provider=%s", settings.feed.provider)
    logger.info("alerts_enabled=%s", settings.alerts.enabled)
    return 0


def _stub(name: str, phase: str) -> Callable[[argparse.Namespace], int]:
    """Build a handler for a command that is not implemented yet."""

    def _handler(_: argparse.Namespace) -> int:
        logger.warning("'%s' is not implemented yet (%s).", name, phase)
        return EXIT_NOT_IMPLEMENTED

    return _handler


def main(argv: Sequence[str] | None = None) -> int:
    """Program entry point. Returns a process exit code."""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
