"""Initialize the DuckDB database from a clean environment.

Creates the database file (if needed), applies all migrations, and optionally
loads seed data, then prints a per-table row-count summary.

    python scripts/init_db.py            # migrate + seed
    python scripts/init_db.py --no-seed  # migrate only

The database path comes from configuration (``EI_DATABASE__PATH``); see
``README.md`` and ``config/README.md``.
"""

from __future__ import annotations

import argparse

from election_intelligence.data.storage import Database
from election_intelligence.utils import configure_logging, get_logger


def main() -> int:
    configure_logging()
    logger = get_logger("init_db")

    parser = argparse.ArgumentParser(description="Initialize the DuckDB database.")
    parser.add_argument(
        "--no-seed", action="store_true", help="Skip loading seed data."
    )
    args = parser.parse_args()

    db = Database()
    try:
        applied = db.initialize(seed=not args.no_seed)
        logger.info("database ready at %s", db.path)
        logger.info("applied %d migration(s): %s", len(applied), applied or "none")
        for table, n in db.table_counts().items():
            logger.info("  %-20s %d rows", table, n)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
