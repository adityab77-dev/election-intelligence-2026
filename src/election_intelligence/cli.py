"""Command-line entry point for election-intelligence-2026.

This is a thin dispatcher wired up as the ``election-intelligence`` console
script (see ``pyproject.toml``). Subcommands are intentionally minimal for now;
feature commands will be registered here as the platform grows.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from election_intelligence import __version__
from election_intelligence.config import get_settings
from election_intelligence.utils import configure_logging, get_logger

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
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

    return parser


def _cmd_info(_: argparse.Namespace) -> int:
    """Report the active environment and key configuration paths."""
    settings = get_settings()
    logger.info("environment=%s", settings.environment.value)
    logger.info("database=%s", settings.database.path)
    logger.info("log_dir=%s", settings.logging.log_dir)
    return 0


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
