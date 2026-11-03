# Phase B — Synthetic vs. Real Poll Forecast Comparison

Generated 2026-11-02 · forecast date 2026-11-02 · seed 2026 · 50,000 simulations.
Real polls: 471 ingested from Wikipedia (421 stored after natural-key dedup).

Both columns run the **identical** pipeline (aggregation → forecast → Monte Carlo);
the only difference is the poll input — `sample_polls.json` (synthetic) vs. the
Wikipedia MediaWiki ingestion. No aggregation/forecast/Monte-Carlo logic changed.

## State polling averages & forecast margins (D − R, points)

Forecast mean equals the weighted poll average (the engine is poll-only).

| State | Synthetic avg | Synthetic forecast | Real avg | Real forecast | Swing |
|-------|:---:|:---:|:---:|:---:|:---:|
| GA | D +1.8 | D +1.8 | **D +8.8** | **D +8.8** | +7.0 D |
| NC | D +2.8 | D +2.8 | **D +10.9** | **D +10.9** | +8.1 D |
| ME | D +0.2 | D +0.2 | **D +4.0** | **D +4.0** | +3.8 D |
| MI | D +3.7 | D +3.7 | **D +4.3** | **D +4.3** | +0.6 D |
| NH | D +5.8 | D +5.8 | **D +7.6** | **D +7.6** | +1.8 D |
| TX | **R +2.4** | R +2.4 | **D +3.3** | D +3.3 | **flips D** |
| OH | **R +1.2** | R +1.2 | **D +3.1** | D +3.1 | **flips D** |
| IA | **R +2.9** | R +2.9 | **D +0.6** | D +0.6 | **flips D** |

The synthetic set had TX/OH/IA leaning Republican; the real Wikipedia polls have
**all eight battlegrounds leaning Democratic**.

## Chamber outputs

| Metric | Synthetic | Real |
|--------|:---:|:---:|
| **Republican Senate control** | **78%** | **27%** |
| **Democratic Senate control** | 22% | **73%** |
| Expected Republican seats | 51.4 | 49.1 |
| Expected Democratic seats | 48.6 | 50.9 |
| Most influential states (top 5) | IA, TX, OH, ME, GA | TX, OH, ME, MI, NH |

**The forecast flips**: synthetic data favored Republicans (78%); real polling data
favors Democrats (73%). Expected Republican seats fall from 51.4 to 49.1 (below the
50-seat control line). The influential-state set shifts accordingly.

## What changed in the code (dashboard only; engines untouched)

- **Banner:** "⚠️ Demo Mode / Synthetic Polling Data" → **"🟢 Real Polling Data"**,
  showing the data source (Wikipedia MediaWiki polling tables), the last-refreshed
  timestamp, and the number of polls ingested.
- **Dashboard data layer:** now surfaces `last_refreshed` (max poll ingest time) and
  the poll count for the banner. No change to how any number is computed.
- **Cloud bootstrap (`streamlit_app.py`):** now ingests from **Wikipedia** instead of
  `sample_polls.json`, removing the live app's dependency on synthetic data. Resilient:
  a failed fetch leaves data untouched and the dashboard shows its no-data guidance.
- **`sample_polls.json`** remains only for offline/demo (`load-polls --source sample`)
  and tests — it is no longer on the production path.

## Verification
- `forecast` + `simulate` run on the real data (471 ingested) → R 27% / D 73%.
- Full test suite: **121 passed**.
- Dashboard data layer reads the real DB: no error, 421 polls, 8 forecasts/aggregates,
  R control 27%, GA forecast D +8.8.
- Streamlit app serves the real-data forecast (health 200).

> Data provenance: polls transcribed from Wikipedia (CC-BY-SA), which cites the original
> pollsters. Pollster grades come from a static table (no live ratings feed). Scheduled
> automated refresh + last-good snapshot are Phase C.
