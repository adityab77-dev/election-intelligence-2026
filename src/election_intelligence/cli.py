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

    init_db = subparsers.add_parser(
        "init-db",
        help="Create the database, run migrations, and load seed data. [Phase 2]",
    )
    init_db.add_argument(
        "--no-seed", action="store_true", help="Skip loading seed data."
    )
    init_db.set_defaults(func=_cmd_init_db)

    load_polls = subparsers.add_parser(
        "load-polls",
        help="Ingest MVP polling data into the database. [Phase 3]",
    )
    load_polls.add_argument(
        "--file",
        default=None,
        help="JSON file of polls (defaults to the bundled MVP sample).",
    )
    load_polls.set_defaults(func=_cmd_load_polls)

    poll_average = subparsers.add_parser(
        "poll-average",
        help="Show the weighted polling aggregate per battleground. [Phase 4]",
    )
    poll_average.add_argument(
        "--state",
        default=None,
        help="Two-letter state code (default: all battlegrounds).",
    )
    poll_average.add_argument(
        "--breakdown",
        action="store_true",
        help="Show the per-poll contribution breakdown.",
    )
    poll_average.set_defaults(func=_cmd_poll_average)

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


def _cmd_init_db(args: argparse.Namespace) -> int:
    """Create the database, run migrations, and (optionally) load seed data."""
    from election_intelligence.data.storage import Database

    db = Database()
    try:
        applied = db.initialize(seed=not args.no_seed)
        logger.info("database ready at %s (applied %d migration(s))", db.path, len(applied))
        for table, n in db.table_counts().items():
            logger.info("  %-20s %d rows", table, n)
    finally:
        db.close()
    return 0


def _cmd_load_polls(args: argparse.Namespace) -> int:
    """Ingest polling data (reference seeds loaded first if the DB is empty)."""
    from election_intelligence.data.ingestion.polls import PollIngestor
    from election_intelligence.data.storage import Database, SeedLoader

    db = Database()
    try:
        db.migrate()
        if db.senate_races.count() == 0:
            logger.info("no races found; loading reference seeds first")
            SeedLoader(db).load_all()
        report = PollIngestor(db).ingest_file(args.file)
        logger.info(
            "ingested %d poll(s), rejected %d", report.ingested, report.rejected
        )
        for identifier, errors in report.errors:
            logger.warning("  rejected %s: %s", identifier, "; ".join(errors))
    finally:
        db.close()
    return 0


def _cmd_poll_average(args: argparse.Namespace) -> int:
    """Print the weighted polling aggregate for one or all battlegrounds."""
    from election_intelligence.aggregation import PollAggregator
    from election_intelligence.data.ingestion.polls import BATTLEGROUND_RACES
    from election_intelligence.data.storage import Database

    if args.state:
        code = args.state.upper()
        if code not in BATTLEGROUND_RACES:
            logger.error("%s is not an MVP battleground state", code)
            return 1
        targets = {code: BATTLEGROUND_RACES[code]}
    else:
        targets = dict(BATTLEGROUND_RACES)

    aggregator = PollAggregator()
    db = Database()
    try:
        for code, race_id in targets.items():
            result = aggregator.aggregate_race(db, race_id, state_code=code)
            if result is None:
                logger.info("%s (%s): no polls loaded", code, race_id)
                continue
            logger.info(
                "%s (%s): weighted D%+.2f  +/-%.2f  (%d polls, N_eff %.1f, through %s)",
                code,
                race_id,
                result.margin,
                result.std_error,
                result.poll_count,
                result.effective_sample_size,
                result.last_updated,
            )
            if args.breakdown:
                for contribution in result.contributions:
                    logger.info(
                        "    %-22s %s  D%+.1f  share %5.1f%%  "
                        "(n=%s q=%.2f r=%.2f)",
                        contribution.pollster,
                        contribution.field_end,
                        contribution.margin,
                        contribution.weight_share * 100,
                        contribution.sample_size,
                        contribution.weight_quality,
                        contribution.weight_recency,
                    )
    finally:
        db.close()
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
