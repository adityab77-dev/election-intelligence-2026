"""Streamlit Community Cloud entry point.

Streamlit Cloud clones the repo into a fresh, ephemeral environment with an empty
filesystem, so the DuckDB database the dashboard reads does not exist yet. This
entry point:

1. puts the ``src/`` package on the import path (no editable install needed);
2. bootstraps **real polling data** once per container by running the existing
   pipeline (seed -> ingest from Wikipedia -> forecast -> simulate); and
3. renders the read-only dashboard.

It adds no new forecasting logic — step 2 only orchestrates committed engines.
Run locally with:  ``streamlit run streamlit_app.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the src-layout package importable without an editable install.
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st


# Tables cleared before a rebuild (FK-safe order: children before parents).
_REBUILD_TABLES = (
    "simulation_results",
    "simulation_runs",
    "state_forecasts",
    "poll_aggregates",
    "polls",
)


@st.cache_resource(show_spinner=False)
def _bootstrap_real_data() -> str:
    """Refresh the database with real Wikipedia polls, once per container.

    Fetches Wikipedia *first*, so a failed fetch leaves any existing data intact.
    On success it **replaces** prior data (so a previous deploy's synthetic
    database, which Streamlit Cloud may keep on reused storage, cannot linger)
    and recomputes forecasts + simulation. Uses only the existing pipeline
    engines; runs once per container via the cache.
    """
    from datetime import date

    from election_intelligence.data.ingestion.polls import (
        BATTLEGROUND_RACES,
        PollIngestor,
    )
    from election_intelligence.data.ingestion.sources import WikipediaPollSource
    from election_intelligence.data.storage import Database, SeedLoader
    from election_intelligence.forecast import ForecastEngine
    from election_intelligence.simulate import MonteCarloEngine

    # Fetch before touching the database so a failure keeps the last good data.
    try:
        polls = WikipediaPollSource().fetch()
    except Exception:  # noqa: BLE001 - never crash the app on a fetch error
        return "fetch-failed"
    if not polls:
        return "no-polls"

    db = Database()
    try:
        db.migrate()
        if db.senate_races.count() == 0:
            SeedLoader(db).load_all()

        # Replace any prior polls/forecasts/runs (incl. a persisted synthetic DB).
        for table in _REBUILD_TABLES:
            db.client.run(f"DELETE FROM {table}")
        PollIngestor(db).ingest(polls)

        engine = ForecastEngine()
        forecast_date = date.today()
        forecasts = []
        for code, race_id in BATTLEGROUND_RACES.items():
            forecast = engine.forecast_race(
                db, race_id, state_code=code, forecast_date=forecast_date
            )
            if forecast is not None:
                engine.persist(db, forecast)
                forecasts.append(forecast)

        if forecasts:
            MonteCarloEngine().run_and_store(db, forecasts)
        return "bootstrapped"
    finally:
        db.close()


# Bootstrap before any Streamlit UI command runs (no UI emitted here, so the
# dashboard's st.set_page_config remains the first UI call).
_bootstrap_real_data()

from election_intelligence.dashboard.app import main  # noqa: E402

main()
