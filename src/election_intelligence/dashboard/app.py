"""Streamlit dashboard entry point.

Run locally with::

    streamlit run src/election_intelligence/dashboard/app.py

This is a placeholder shell that wires up configuration and logging and renders
a landing page. Visualisations and interactive controls will be added later.
"""

from __future__ import annotations

from election_intelligence import __version__
from election_intelligence.config import get_settings
from election_intelligence.utils import configure_logging, get_logger


def main() -> None:
    """Render the dashboard landing page."""
    import streamlit as st

    configure_logging()
    logger = get_logger(__name__)
    settings = get_settings()

    st.set_page_config(
        page_title="Election Intelligence 2026",
        page_icon="📊",
        layout="wide",
    )

    st.title("Election Intelligence 2026")
    st.caption(f"v{__version__} · environment: {settings.environment.value}")
    st.info("Dashboard scaffold — forecasting views coming soon.")

    logger.debug("rendered dashboard landing page")


if __name__ == "__main__":
    main()
