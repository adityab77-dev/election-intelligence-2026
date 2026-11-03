"""Streamlit Community Cloud entry point.

Streamlit Cloud clones the repo into a fresh, ephemeral environment with an empty
filesystem, so the DuckDB database the dashboard reads does not exist yet. This
entry point:

1. puts the ``src/`` package on the import path (no editable install needed);
2. bootstraps the **synthetic demo data** once per container by running the
   existing pipeline (seed -> ingest -> forecast -> simulate); and
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


@st.cache_resource(show_spinner=False)
def _bootstrap_demo_data() -> str:
    """Populate the database with synthetic demo data once per container.

    Idempotent: if a simulation run already exists, it does nothing. Uses only
    the existing pipeline engines. Returns a short status string.
    """
    from datetime import date

    from election_intelligence.data.ingestion.polls import (
        BATTLEGROUND_RACES,
        PollIngestor,
    )
    from election_intelligence.data.storage import Database, SeedLoader
    from election_intelligence.forecast import ForecastEngine
    from election_intelligence.simulate import MonteCarloEngine

    db = Database()
    try:
        db.migrate()
        if db.simulation_runs.count() > 0:
            return "existing"

        SeedLoader(db).load_all()
        PollIngestor(db).ingest_file()

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

        MonteCarloEngine().run_and_store(db, forecasts)
        return "bootstrapped"
    finally:
        db.close()


# Bootstrap before any Streamlit UI command runs (no UI emitted here, so the
# dashboard's st.set_page_config remains the first UI call).
_bootstrap_demo_data()

from election_intelligence.dashboard.app import main  # noqa: E402

main()
