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
        "--source",
        choices=["sample", "wikipedia"],
        default="sample",
        help="Poll source: 'sample' (synthetic) or 'wikipedia' (real). [Phase A]",
    )
    load_polls.add_argument(
        "--file",
        default=None,
        help="JSON file of polls (sample source only; defaults to the bundled MVP sample).",
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

    forecast = subparsers.add_parser(
        "forecast",
        help="Generate state forecast distributions from poll aggregates. [Phase 5]",
    )
    forecast.add_argument(
        "--state",
        default=None,
        help="Two-letter state code (default: all battlegrounds).",
    )
    forecast.add_argument(
        "--date",
        default=None,
        help="Forecast date YYYY-MM-DD (default: today).",
    )
    forecast.add_argument(
        "--no-store",
        action="store_true",
        help="Compute and print forecasts without persisting them.",
    )
    forecast.set_defaults(func=_cmd_forecast)

    simulate = subparsers.add_parser(
        "simulate",
        help="Run the correlated Monte Carlo and compute Senate control. [Phase 6]",
    )
    simulate.add_argument(
        "--sims", type=int, default=None, help="Number of simulations (default 50000)."
    )
    simulate.add_argument(
        "--seed", type=int, default=None, help="Random seed (default 2026)."
    )
    simulate.add_argument(
        "--date",
        default=None,
        help="Forecast date YYYY-MM-DD used for on-the-fly forecasts.",
    )
    simulate.add_argument(
        "--no-store",
        action="store_true",
        help="Run without persisting the simulation.",
    )
    simulate.set_defaults(func=_cmd_simulate)

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
        if args.source == "wikipedia":
            from election_intelligence.data.ingestion.sources import WikipediaPollSource

            logger.info("fetching real polls from Wikipedia (this may take ~30s)...")
            report = PollIngestor(db).ingest(WikipediaPollSource().fetch())
        else:
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


def _cmd_forecast(args: argparse.Namespace) -> int:
    """Generate (and optionally store) forecast distributions per battleground."""
    from datetime import date

    from election_intelligence.data.ingestion.polls import BATTLEGROUND_RACES
    from election_intelligence.data.storage import Database
    from election_intelligence.forecast import ForecastEngine

    if args.state:
        code = args.state.upper()
        if code not in BATTLEGROUND_RACES:
            logger.error("%s is not an MVP battleground state", code)
            return 1
        targets = {code: BATTLEGROUND_RACES[code]}
    else:
        targets = dict(BATTLEGROUND_RACES)

    forecast_date: date | None = None
    if args.date:
        try:
            forecast_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("invalid --date %r (expected YYYY-MM-DD)", args.date)
            return 1

    engine = ForecastEngine()
    db = Database()
    try:
        db.migrate()
        for code, race_id in targets.items():
            result = engine.forecast_race(
                db, race_id, state_code=code, forecast_date=forecast_date
            )
            if result is None:
                logger.info("%s (%s): no polls loaded -> no forecast", code, race_id)
                continue
            logger.info(
                "%s (%s): D%+.1f  sigma %.1f  confidence %s",
                code,
                race_id,
                result.mean_margin,
                result.sigma,
                result.confidence_level.value,
            )
            if not args.no_store:
                engine.persist(db, result)
    finally:
        db.close()
    return 0


def _git_short_sha() -> str | None:
    """Best-effort current git short SHA for run metadata; None if unavailable."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _cmd_simulate(args: argparse.Namespace) -> int:
    """Run the Monte Carlo over the battleground forecasts and report control."""
    from datetime import date

    from election_intelligence.data.ingestion.polls import BATTLEGROUND_RACES
    from election_intelligence.data.storage import Database
    from election_intelligence.forecast import ForecastEngine
    from election_intelligence.simulate import MonteCarloEngine, SimulationConfig

    forecast_date: date | None = None
    if args.date:
        try:
            forecast_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("invalid --date %r (expected YYYY-MM-DD)", args.date)
            return 1

    config_kwargs: dict[str, int] = {}
    if args.sims is not None:
        config_kwargs["n_simulations"] = args.sims
    if args.seed is not None:
        config_kwargs["random_seed"] = args.seed
    config = SimulationConfig(**config_kwargs)

    db = Database()
    try:
        db.migrate()
        forecast_engine = ForecastEngine()
        forecasts = []
        for code, race_id in BATTLEGROUND_RACES.items():
            stored = db.state_forecasts.latest_for_race(race_id)
            result = stored or forecast_engine.forecast_race(
                db, race_id, state_code=code, forecast_date=forecast_date
            )
            if result is not None:
                forecasts.append(result)

        if not forecasts:
            logger.error(
                "no forecasts available; run 'load-polls' (and 'forecast') first"
            )
            return 1

        engine = MonteCarloEngine(config)
        code_version = _git_short_sha()
        if args.no_store:
            output = engine.simulate(forecasts, code_version=code_version)
        else:
            output = engine.run_and_store(db, forecasts, code_version=code_version)

        logger.info("Republican Senate: %.0f%%", output.prob_rep_control * 100)
        logger.info("Democratic Senate: %.0f%%", output.prob_dem_control * 100)
        logger.info("50-50 Senate (tie): %.1f%%", output.prob_tie * 100)
        logger.info(
            "Expected Seats: R %.1f  D %.1f",
            output.expected_rep_seats,
            output.expected_dem_seats,
        )
        logger.info(
            "R seats: %d (p10) / %d (median) / %d (p90)",
            output.rep_seats_p10,
            output.rep_seats_median,
            output.rep_seats_p90,
        )
        logger.info(
            "MC std error %.3f pp | convergence delta %.3f pp | %d sims",
            output.mc_std_error,
            output.convergence_delta,
            output.n_simulations,
        )
        logger.info("Most influential states:")
        for item in output.influential_states[:5]:
            logger.info("  %-4s leverage %+.3f", item["state"], item["leverage"])
        if not args.no_store:
            logger.info(
                "stored run %s (seed %d, code %s)",
                output.run_id,
                output.random_seed,
                output.code_version or "unknown",
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
