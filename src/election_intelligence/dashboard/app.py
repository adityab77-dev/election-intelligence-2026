"""Streamlit dashboard for the 2026 Senate Control Intelligence System.

Run locally with::

    streamlit run src/election_intelligence/dashboard/app.py

This is a **read-only** visualization of the forecast already produced by the
pipeline. It opens DuckDB read-only, reads the latest stored simulation run,
forecasts, and polls, and renders them. It adds no forecasting logic, no
election-night logic, and never writes to the database. The poll-aggregates
table is computed for display from stored polls via the existing Phase 4
aggregator (a read-only operation).

Populate the data first::

    election-intelligence init-db
    election-intelligence load-polls
    election-intelligence forecast
    election-intelligence simulate
"""

from __future__ import annotations

from typing import Any

from election_intelligence import __version__
from election_intelligence.utils import configure_logging, get_logger

logger = get_logger(__name__)


def _format_margin(margin: float) -> str:
    """Render a D-R margin as e.g. 'D +1.8' or 'R +2.4'."""
    party = "D" if margin >= 0 else "R"
    return f"{party} +{abs(margin):.1f}"


def _load_data() -> dict[str, Any]:
    """Read everything the dashboard needs from DuckDB (read-only)."""
    from election_intelligence.aggregation import PollAggregator
    from election_intelligence.data.ingestion.polls import BATTLEGROUND_RACES
    from election_intelligence.data.storage import Database

    data: dict[str, Any] = {
        "error": None,
        "run": None,
        "result": None,
        "forecasts": [],
        "aggregates": [],
        "polls_loaded": 0,
    }

    db = Database(read_only=True)
    try:
        data["polls_loaded"] = db.polls.count()  # first access -> connects
        run = db.simulation_runs.latest()
        data["run"] = run
        if run is not None:
            data["result"] = db.simulation_results.get(run.run_id)

        aggregator = PollAggregator()
        for code, race_id in BATTLEGROUND_RACES.items():
            forecast = db.state_forecasts.latest_for_race(race_id)
            if forecast is not None:
                data["forecasts"].append(forecast)
            aggregate = aggregator.aggregate_race(db, race_id, state_code=code)
            if aggregate is not None:
                data["aggregates"].append(aggregate)
    except Exception as exc:  # noqa: BLE001 - surface any read error as guidance
        data["error"] = (
            f"Could not read the database ({exc}). Run the pipeline first: "
            "`init-db`, `load-polls`, `forecast`, `simulate`."
        )
    finally:
        db.close()
    return data


def _render_control_and_seats(st: Any, result: Any) -> None:
    st.subheader("Senate Control Probability")
    col_r, col_d = st.columns(2)
    col_r.metric("Republican Senate", f"{result.prob_rep_control * 100:.0f}%")
    col_d.metric("Democratic Senate", f"{result.prob_dem_control * 100:.0f}%")

    st.subheader("Expected Seats")
    col_er, col_ed = st.columns(2)
    if result.expected_rep_seats is not None:
        col_er.metric("Expected Republican seats", f"{result.expected_rep_seats:.1f}")
    if result.expected_dem_seats is not None:
        col_ed.metric("Expected Democratic seats", f"{result.expected_dem_seats:.1f}")

    if result.seat_histogram:
        import pandas as pd

        hist = result.seat_histogram
        frame = (
            pd.DataFrame(
                {
                    "R seats": [int(k) for k in hist],
                    "Probability": [float(v) for v in hist.values()],
                }
            )
            .sort_values("R seats")
            .set_index("R seats")
        )
        st.caption("Distribution of simulated Republican seats")
        st.bar_chart(frame)


def _render_state_forecasts(st: Any, forecasts: list[Any]) -> None:
    import pandas as pd

    st.subheader("State Forecasts")
    if not forecasts:
        st.info("No forecasts stored. Run `election-intelligence forecast`.")
        return
    rows = [
        {
            "State": fc.state_code or fc.race_id,
            "Mean Margin": _format_margin(fc.mean_margin),
            "Sigma": round(fc.sigma, 2),
            "Confidence": fc.confidence_level.value,
            "Poll Count": fc.poll_count,
        }
        for fc in forecasts
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _render_poll_aggregates(st: Any, aggregates: list[Any]) -> None:
    import pandas as pd

    st.subheader("Poll Aggregates")
    if not aggregates:
        st.info("No polls loaded. Run `election-intelligence load-polls`.")
        return
    rows = [
        {
            "State": agg.state_code or agg.race_id,
            "Weighted Margin": _format_margin(agg.margin),
            "Variance": round(agg.variance, 2),
            "Poll Count": agg.poll_count,
            "Last Updated": str(agg.last_updated),
        }
        for agg in aggregates
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _render_influential_states(st: Any, result: Any) -> None:
    import pandas as pd

    st.subheader("Most Influential States")
    st.caption(
        "Control leverage = P(R control | R wins state) - P(R control | D wins state)"
    )
    influential = result.influential_states or []
    if not influential:
        st.info("No influence data in the latest run.")
        return
    frame = pd.DataFrame(influential)
    display = frame[["state", "leverage"]].rename(
        columns={"state": "State", "leverage": "Leverage"}
    )
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.bar_chart(frame.set_index("state")[["leverage"]])


def _render_metadata(st: Any, run: Any) -> None:
    st.subheader("Simulation Metadata")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Simulations", f"{run.n_simulations:,}")
    col2.metric("Seed", str(run.random_seed))
    col3.metric("Code Version", run.code_version or "unknown")
    timestamp = run.finished_at or run.created_at
    col4.metric("Generated", timestamp.strftime("%Y-%m-%d %H:%M") if timestamp else "-")


def _render_methodology(st: Any) -> None:
    st.header("Methodology")
    st.markdown(
        """
### Poll ingestion
Polls for the eight Senate battleground states (GA, NC, ME, MI, NH, TX, OH, IA)
are validated (battleground-only, no post-election dates, plausible margins and
sample sizes) and stored in DuckDB. Margins are expressed as **D − R** in points.

> The bundled sample polls are **synthetic development data**, not real polls.

### Poll weighting
Each poll's weight is the product of three factors:
- **Sample size** — `sqrt(min(n, 1500))` (larger polls count more, with a cap).
- **Recency** — `0.5 ^ (age / 14 days)` (exponential decay, 14-day half-life).
- **Pollster quality** — a multiplier from the pollster's letter grade
  (A+ = 1.0 … F = 0.1; unknown = 0.5).

The weighted mean is the aggregate margin; its variance combines the sampling
error of the weighted mean with the weighted dispersion between polls.

### Forecast generation
Each race becomes a distribution `Normal(mean, sigma)`:
- **mean** = the weighted poll margin.
- **sigma** = `sqrt(poll_variance + base_miss² + thin_penalty² + staleness²)`,
  where `base_miss = 3.5` points is a systematic polling-miss floor, with extra
  uncertainty for thinly or stale-polled races.
- **Confidence** (High / Medium / Low) is derived from sigma and poll count.

### Monte Carlo methodology
50,000+ correlated simulations. In each: one **shared national error**
(σ = 3.0, all states together) plus an **independent state error** per race.
The forecast sigma is split into these two components, so correlation is added
without inflating marginal uncertainty:

`state_margin = mean + national_error + state_error`

A state goes Republican if its drawn margin < 0. Seats are counted as
`48 (baseline) + Republican battleground wins`; Republicans control at **≥ 50**
(VP tiebreak), Democrats at **≥ 51**. The control probability is the share of
simulations in which each party controls. Runs are reproducible by random seed.

### Assumptions
- Only the eight battlegrounds are simulated; all other seats are a fixed
  baseline (48 R / 44 D — the 53-47 Senate minus the battlegrounds' current holders).
- Errors are Normal (no fat tails); national σ = 3.0, base polling miss = 3.5 pt.
- The bundled polling data is synthetic.

### Limitations
- **No fundamentals model** (polls only) and **no hierarchical pooling**.
- **No RCV / runoff modelling** (Maine, Alaska, Georgia resolution rules).
- **No election-night / live-results** updating.
- Normal (not Student-t) error terms understate true tail (wave) risk.
- The non-battleground baseline is fixed, not read from a full Senate roster.
"""
    )


def _render_dashboard(st: Any, data: dict[str, Any]) -> None:
    if data["error"]:
        st.error(data["error"])
        return

    result = data["result"]
    run = data["run"]
    if result is None or run is None:
        st.warning(
            "No simulation found yet. Run the pipeline: "
            "`init-db` -> `load-polls` -> `forecast` -> `simulate`."
        )
    else:
        _render_control_and_seats(st, result)
        st.divider()

    _render_state_forecasts(st, data["forecasts"])
    st.divider()
    _render_poll_aggregates(st, data["aggregates"])

    if result is not None:
        st.divider()
        _render_influential_states(st, result)
        st.divider()
        _render_metadata(st, run)


def main() -> None:
    """Render the dashboard."""
    import streamlit as st

    configure_logging()

    st.set_page_config(
        page_title="Election Intelligence 2026",
        page_icon="📊",
        layout="wide",
    )
    st.title("2026 Senate Control Intelligence")
    st.caption(f"v{__version__} · read-only forecast dashboard")

    st.warning(
        "**⚠️ Demo Mode**\n\n"
        "This release uses **synthetic polling data** for forecasting-engine "
        "validation.\n\n"
        "The forecasting pipeline, poll aggregation, forecast engine, and Monte "
        "Carlo simulation are **real**.\n\n"
        "Live polling integration is planned for a future release."
    )

    data = _load_data()

    dashboard_tab, methodology_tab = st.tabs(["Dashboard", "Methodology"])
    with dashboard_tab:
        _render_dashboard(st, data)
    with methodology_tab:
        _render_methodology(st)

    logger.debug("rendered dashboard")


if __name__ == "__main__":
    main()
