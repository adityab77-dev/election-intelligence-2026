"""Streamlit dashboard for the 2026 Senate Control Intelligence System.

Run locally with::

    streamlit run src/election_intelligence/dashboard/app.py

A **read-only**, presentation-focused view of the forecast the pipeline already
produced. It opens DuckDB read-only, reads the latest stored simulation and
forecasts, and renders a polished, card-based layout. It adds **no forecasting
logic**: per-state win probabilities shown here are read off the existing
forecast distributions (``P(D win) = Phi(mean / sigma)``), a display transform
only. The aggregation, forecast, Monte Carlo engines and the database schema are
untouched.
"""

from __future__ import annotations

import math
from typing import Any

from election_intelligence import __version__
from election_intelligence.utils import configure_logging, get_logger

logger = get_logger(__name__)

# --- palette ----------------------------------------------------------------
DEM = "#2563eb"
REP = "#dc2626"
TIE = "#7c3aed"
RATINGS = {
    "Strong D": "#1e3a8a",
    "Lean D": "#60a5fa",
    "Toss-Up": "#6b7280",
    "Lean R": "#f87171",
    "Strong R": "#991b1b",
}
STATE_NAMES = {
    "GA": "Georgia", "NC": "North Carolina", "ME": "Maine", "MI": "Michigan",
    "NH": "New Hampshire", "TX": "Texas", "OH": "Ohio", "IA": "Iowa",
}

CSS = """
<style>
.ei-row { display:flex; flex-wrap:wrap; gap:14px; margin:8px 0 4px; }
.ei-prob { flex:1 1 150px; text-align:center; border-radius:16px; padding:18px 12px; color:#fff; }
.ei-prob .lbl { font-size:0.72rem; letter-spacing:0.06em; text-transform:uppercase; opacity:0.9; }
.ei-prob .big { font-size:2.8rem; font-weight:800; line-height:1.05; }
.ei-prob .sub { font-size:0.8rem; opacity:0.9; }
.ei-bar { display:flex; height:30px; border-radius:8px; overflow:hidden; font-weight:700;
          color:#fff; font-size:0.82rem; margin:6px 0 2px; }
.ei-bar > div { display:flex; align-items:center; justify-content:center; min-width:34px; }
.ei-card { flex:1 1 220px; background:rgba(128,128,128,0.08);
           border:1px solid rgba(128,128,128,0.22); border-radius:14px; padding:14px 16px; }
.ei-card .hd { font-weight:700; font-size:1.05rem; margin-bottom:2px; }
.ei-card .mut { opacity:0.72; font-size:0.85rem; }
.ei-chip { display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.74rem;
           font-weight:700; color:#fff; white-space:nowrap; }
.ei-meta { display:flex; flex-wrap:wrap; gap:22px; opacity:0.8; font-size:0.85rem; margin:2px 0 10px; }
.ei-lay { font-size:1.02rem; padding:10px 14px; border-left:4px solid #2563eb;
          background:rgba(37,99,235,0.07); border-radius:6px; margin:6px 0 4px; }
table.ei { width:100%; border-collapse:collapse; font-size:0.9rem; }
table.ei th { text-align:left; padding:9px 10px; border-bottom:2px solid rgba(128,128,128,0.3);
              font-size:0.72rem; letter-spacing:0.04em; text-transform:uppercase; opacity:0.7; }
table.ei td { padding:9px 10px; border-bottom:1px solid rgba(128,128,128,0.16); }
table.ei tr:last-child td { border-bottom:none; }
.ei-rank { font-weight:800; opacity:0.45; margin-right:8px; }
</style>
"""


# --- display helpers (no forecasting logic) ---------------------------------
def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _p_dem(mean: float, sigma: float) -> float:
    return _phi(mean / sigma) if sigma > 0 else (1.0 if mean > 0 else 0.0)


def _rating(p_dem: float) -> str:
    if p_dem >= 0.85:
        return "Strong D"
    if p_dem >= 0.60:
        return "Lean D"
    if p_dem > 0.40:
        return "Toss-Up"
    if p_dem > 0.15:
        return "Lean R"
    return "Strong R"


def _fmt_margin(mean: float) -> str:
    return f"{'D' if mean >= 0 else 'R'} +{abs(mean):.1f}"


def _state_name(code: str | None) -> str:
    return STATE_NAMES.get(code or "", code or "—")


def _tie_probability(result: Any) -> float:
    stored = getattr(result, "prob_tie", None)
    if stored is not None:
        return float(stored)
    return float((result.seat_histogram or {}).get("50", 0.0))


def _load_data() -> dict[str, Any]:
    from election_intelligence.aggregation import PollAggregator
    from election_intelligence.data.ingestion.polls import BATTLEGROUND_RACES
    from election_intelligence.data.storage import Database

    data: dict[str, Any] = {
        "error": None, "run": None, "result": None, "forecasts": [],
        "aggregates": [], "polls_loaded": 0, "last_refreshed": None,
        "snapshots": [], "live_timeline": [], "live_mode": False,
    }
    db = Database(read_only=True)
    try:
        data["polls_loaded"] = db.polls.count()
        refreshed = db.client.fetch_one("SELECT max(ingested_at) AS t FROM polls")
        data["last_refreshed"] = refreshed["t"] if refreshed else None
        run = db.simulation_runs.latest()
        data["run"] = run
        if run is not None:
            data["result"] = db.simulation_results.get(run.run_id)
            data["live_mode"] = run.regime.value == "live"
        aggregator = PollAggregator()
        for code, race_id in BATTLEGROUND_RACES.items():
            forecast = db.state_forecasts.latest_for_race(race_id)
            if forecast is not None:
                data["forecasts"].append(forecast)
            aggregate = aggregator.aggregate_race(db, race_id, state_code=code)
            if aggregate is not None:
                data["aggregates"].append(aggregate)
            snapshot = db.reporting_snapshots.latest_for_race(race_id)
            if snapshot is not None:
                data["snapshots"].append((code, snapshot))
        data["live_timeline"] = db.client.fetch_all(
            "SELECT r.created_at AS t, res.prob_dem_control AS dem, "
            "res.prob_rep_control AS rep, res.prob_tie AS tie "
            "FROM simulation_runs r JOIN simulation_results res ON r.run_id = res.run_id "
            "WHERE r.regime = 'live' ORDER BY r.created_at"
        )
    except Exception as exc:  # noqa: BLE001
        data["error"] = (
            f"Could not read the database ({exc}). The forecast is still being "
            "prepared — check back in a moment."
        )
    finally:
        db.close()
    return data


# --- sections ---------------------------------------------------------------
def _render_header(st: Any, data: dict[str, Any]) -> None:
    result = data["result"]
    polls = data.get("polls_loaded", 0)
    refreshed = data.get("last_refreshed")
    stamp = refreshed.strftime("%Y-%m-%d %H:%M %Z") if refreshed else "unknown"

    p_d = result.prob_dem_control * 100
    p_r = result.prob_rep_control * 100
    p_t = _tie_probability(result) * 100

    st.markdown("## 2026 U.S. Senate Forecast")
    st.markdown(
        '<div class="ei-row">'
        f'<div class="ei-prob" style="background:{DEM}"><div class="lbl">Democratic control</div>'
        f'<div class="big">{p_d:.0f}%</div></div>'
        f'<div class="ei-prob" style="background:{REP}"><div class="lbl">Republican control</div>'
        f'<div class="big">{p_r:.0f}%</div></div>'
        f'<div class="ei-prob" style="background:{TIE}"><div class="lbl">50-50 tie</div>'
        f'<div class="big">{p_t:.1f}%</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ei-meta">'
        f"<span>📊 <b>{polls:,}</b> polls</span>"
        f"<span>🕒 Last refresh: <b>{stamp}</b></span>"
        "<span>🌐 Source: <b>Wikipedia MediaWiki polling tables</b></span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if result.prob_dem_control >= 0.60:
        favored = "Democrats are currently favored to control the Senate"
    elif result.prob_dem_control <= 0.40:
        favored = "Republicans are currently favored to control the Senate"
    else:
        favored = "control of the Senate is a true toss-up"
    st.markdown(
        f'<div class="ei-lay">Based on <b>{polls:,}</b> recent polls across 8 '
        f"battleground states, {favored}.</div>",
        unsafe_allow_html=True,
    )


def _render_probability_bar(st: Any, result: Any) -> None:
    p_d = result.prob_dem_control * 100
    p_r = result.prob_rep_control * 100
    st.markdown("#### Control probability")
    st.markdown(
        '<div class="ei-bar">'
        f'<div style="width:{p_d:.1f}%;background:{DEM}">D {p_d:.0f}%</div>'
        f'<div style="width:{p_r:.1f}%;background:{REP}">R {p_r:.0f}%</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_expected_seats(st: Any, result: Any) -> None:
    import pandas as pd

    st.markdown("### Expected Seats")
    er = result.expected_rep_seats
    ed = result.expected_dem_seats
    st.markdown(
        '<div class="ei-row">'
        f'<div class="ei-card"><div class="mut">Expected Democratic seats</div>'
        f'<div class="hd" style="color:{DEM};font-size:1.8rem">{ed:.1f}</div></div>'
        f'<div class="ei-card"><div class="mut">Expected Republican seats</div>'
        f'<div class="hd" style="color:{REP};font-size:1.8rem">{er:.1f}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    hist = {int(k): float(v) for k, v in (result.seat_histogram or {}).items()}
    if hist:
        top = sorted(hist.items(), key=lambda kv: kv[1], reverse=True)[:3]
        cards = "".join(
            f'<div class="ei-card" style="text-align:center">'
            f'<div class="hd" style="font-size:1.5rem">{100 - s}D–{s}R</div>'
            f'<div class="mut">{p * 100:.0f}% of simulations</div></div>'
            for s, p in top
        )
        st.markdown("#### Most likely outcomes")
        st.markdown(f'<div class="ei-row">{cards}</div>', unsafe_allow_html=True)

        frame = (
            pd.DataFrame({"R seats": list(hist), "Probability": list(hist.values())})
            .sort_values("R seats")
            .set_index("R seats")
        )
        st.caption("Distribution of simulated Republican seats")
        st.bar_chart(frame, color=REP)


def _render_battlegrounds(st: Any, forecasts: list[Any]) -> None:
    st.markdown("### Battleground States")
    if not forecasts:
        st.info("Forecasts are being prepared.")
        return
    ordered = sorted(forecasts, key=lambda f: _p_dem(f.mean_margin, f.sigma), reverse=True)
    rows = ""
    for f in ordered:
        p_d = _p_dem(f.mean_margin, f.sigma)
        leader = "D" if f.mean_margin >= 0 else "R"
        lead_color = DEM if leader == "D" else REP
        p_win = max(p_d, 1 - p_d) * 100
        rating = _rating(p_d)
        rows += (
            "<tr>"
            f'<td><b>{_state_name(f.state_code)}</b></td>'
            f'<td style="color:{lead_color};font-weight:700">{leader}</td>'
            f"<td>{_fmt_margin(f.mean_margin)}</td>"
            f"<td>{p_win:.0f}%</td>"
            f"<td>{f.sigma:.1f}</td>"
            f"<td>{f.poll_count}</td>"
            f'<td><span class="ei-chip" style="background:{RATINGS[rating]}">{rating}</span></td>'
            "</tr>"
        )
    st.markdown(
        '<table class="ei"><thead><tr><th>State</th><th>Leader</th><th>Margin</th>'
        "<th>Win prob.</th><th>Sigma</th><th>Polls</th><th>Rating</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )


def _render_influential(st: Any, result: Any, forecasts: list[Any]) -> None:
    st.markdown("### Why the model thinks this")
    st.caption(
        "Most influential states — how often each one decides which party reaches 50 seats."
    )
    by_state = {f.state_code: f for f in forecasts}
    cards = ""
    for i, item in enumerate((result.influential_states or [])[:5], start=1):
        code = item.get("state")
        name = _state_name(code)
        fc = by_state.get(code)
        close = fc is not None and abs(fc.mean_margin) < 4.0
        if close:
            why = (
                f"{name} is close enough that it frequently determines which party "
                "reaches 50 seats."
            )
        else:
            why = (
                f"{name} carries enough weight that flipping it meaningfully shifts "
                "the balance of power."
            )
        cards += (
            f'<div class="ei-card"><div class="hd"><span class="ei-rank">#{i}</span>{name}</div>'
            f'<div class="mut">{why}</div></div>'
        )
    st.markdown(f'<div class="ei-row">{cards}</div>', unsafe_allow_html=True)


def _render_state_details(st: Any, forecasts: list[Any]) -> None:
    st.markdown("### State Detail")
    ordered = sorted(forecasts, key=lambda f: _p_dem(f.mean_margin, f.sigma), reverse=True)
    cards = ""
    for f in ordered:
        p_d = _p_dem(f.mean_margin, f.sigma)
        leader_party = "Democratic" if f.mean_margin >= 0 else "Republican"
        p_win = max(p_d, 1 - p_d)
        accent = DEM if f.mean_margin >= 0 else REP
        explanation = (
            f"{leader_party} advantage of {abs(f.mean_margin):.1f} points. "
            f"Current estimate gives {leader_party}s approximately "
            f"{p_win * 100:.0f}% odds of winning this race."
        )
        cards += (
            f'<div class="ei-card" style="border-left:5px solid {accent}">'
            f'<div class="hd">{_state_name(f.state_code)}</div>'
            f'<div class="mut">Forecast {_fmt_margin(f.mean_margin)} · '
            f"Win prob. {p_win * 100:.0f}% · {f.confidence_level.value} confidence · "
            f"{f.poll_count} polls</div>"
            f'<div style="margin-top:6px">{explanation}</div></div>'
        )
    st.markdown(f'<div class="ei-row">{cards}</div>', unsafe_allow_html=True)


def _render_live_results(st: Any, data: dict[str, Any]) -> None:
    import pandas as pd

    st.markdown("## Live Election Results")
    st.caption("Source: Wikipedia election results")

    snapshots = data.get("snapshots", [])
    if not snapshots:
        st.info(
            "No results reported yet — the forecast is **poll-based**. This view "
            "fills in automatically as Wikipedia's result tables are populated "
            "during counting."
        )
        return

    result = data.get("result")
    if data.get("live_mode") and result is not None:
        st.markdown("#### Live Senate control (polls + counted votes)")
        st.markdown(
            '<div class="ei-row">'
            f'<div class="ei-prob" style="background:{DEM}"><div class="lbl">Democratic</div>'
            f'<div class="big">{result.prob_dem_control * 100:.0f}%</div></div>'
            f'<div class="ei-prob" style="background:{REP}"><div class="lbl">Republican</div>'
            f'<div class="big">{result.prob_rep_control * 100:.0f}%</div></div>'
            f'<div class="ei-prob" style="background:{TIE}"><div class="lbl">50-50 tie</div>'
            f'<div class="big">{_tie_probability(result) * 100:.1f}%</div></div>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("#### Reporting by state")
    rows = ""
    for code, snap in sorted(snapshots, key=lambda cs: cs[1].percent_reporting, reverse=True):
        leader = snap.leader_party.value[0] if snap.leader_party else "—"
        lead_color = DEM if leader == "D" else REP
        call = (
            f'<span class="ei-chip" style="background:{lead_color}">CALLED {leader}</span>'
            if snap.is_called else '<span class="mut">—</span>'
        )
        rows += (
            "<tr>"
            f"<td><b>{_state_name(code)}</b></td>"
            f"<td>{snap.percent_reporting:.0f}%</td>"
            f'<td style="color:{DEM}">{snap.dem_votes:,}</td>'
            f'<td style="color:{REP}">{snap.rep_votes:,}</td>'
            f'<td style="color:{lead_color};font-weight:700">{_fmt_margin(snap.margin or 0.0)}</td>'
            f"<td>{call}</td>"
            "</tr>"
        )
    st.markdown(
        '<table class="ei"><thead><tr><th>State</th><th>Reporting</th>'
        "<th>Dem votes</th><th>Rep votes</th><th>Margin</th><th>Call</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )

    timeline = data.get("live_timeline", [])
    if len(timeline) >= 2:
        st.markdown("#### Senate control over time")
        frame = pd.DataFrame(
            {
                "time": [r["t"] for r in timeline],
                "Democratic": [float(r["dem"]) * 100 for r in timeline],
                "Republican": [float(r["rep"]) * 100 for r in timeline],
            }
        ).set_index("time")
        st.line_chart(frame, color=[DEM, REP])


def _render_methodology(st: Any) -> None:
    st.header("Methodology")
    st.markdown(
        """
This forecast is built in four plain steps, repeated every refresh.

#### 1 · Poll collection
Recent polls for the eight battleground Senate races are gathered automatically
from **Wikipedia's polling tables** (which cite the original pollsters). For each
race we use the current head-to-head matchup between the Democratic and
Republican candidates.

#### 2 · Poll weighting
Not every poll counts the same. A poll counts for more when it is **recent**, has
a **larger sample**, and comes from a **higher-quality pollster**. We combine all
of a state's polls into one weighted average margin.

#### 3 · Forecast
Each state's average becomes a *range* rather than a single number, because polls
are never exact. The range is wider when there are few polls or they disagree, and
always allows for the kind of across-the-board polling miss that happens in real
elections.

#### 4 · Simulation
We play out the election **tens of thousands of times**. In each run, every state
gets a slightly different result (with a shared national swing so the states move
together, like they do in reality), seats are tallied, and we record who controls
the chamber. The headline percentages are simply **how often each party wins**
across all those runs.

#### Reading the numbers
- **Control probability** — the share of simulations a party controls the Senate.
- **50-50 tie** — the chance of an exactly split chamber (which the sitting
  Vice-President would break).
- **Win probability** (per state) — how often that state's favorite wins.
- Nothing here is a certainty; a 70% favorite still loses about three times in ten.

*Data is community-transcribed from Wikipedia; pollster quality grades come from a
static reference table. This is an analytical demonstration, not an official forecast.*
"""
    )


def _render_dashboard(st: Any, data: dict[str, Any]) -> None:
    if data["error"]:
        st.error(data["error"])
        return
    result, run = data["result"], data["run"]
    if result is None or run is None:
        st.warning("The forecast is being prepared — please refresh in a moment.")
        _render_battlegrounds(st, data["forecasts"])
        return

    _render_header(st, data)
    _render_probability_bar(st, result)
    st.divider()
    _render_expected_seats(st, result)
    st.divider()
    _render_battlegrounds(st, data["forecasts"])
    st.divider()
    _render_influential(st, result, data["forecasts"])
    st.divider()
    _render_state_details(st, data["forecasts"])


def main() -> None:
    """Render the dashboard."""
    import streamlit as st

    configure_logging()
    st.set_page_config(
        page_title="2026 Senate Forecast", page_icon="🗳️", layout="wide"
    )
    st.markdown(CSS, unsafe_allow_html=True)

    data = _load_data()
    forecast_tab, live_tab, methodology_tab = st.tabs(
        ["Forecast", "Live Results", "Methodology"]
    )
    with forecast_tab:
        _render_dashboard(st, data)
    with live_tab:
        if data.get("error"):
            st.error(data["error"])
        else:
            _render_live_results(st, data)
    with methodology_tab:
        _render_methodology(st)
    st.caption(f"2026 Senate Control Intelligence · v{__version__} · read-only")

    # Auto-refresh the page every 5 minutes so live results update on their own.
    try:
        import streamlit.components.v1 as components

        components.html(
            "<script>setTimeout(function(){window.parent.location.reload();},"
            "300000);</script>",
            height=0,
        )
    except Exception:  # noqa: BLE001 - cosmetic; never break the page
        pass

    logger.debug("rendered dashboard")


if __name__ == "__main__":
    main()
