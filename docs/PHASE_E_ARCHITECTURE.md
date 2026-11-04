# Phase E — Election-Night Results Engine (Revised: Real-Source Architecture)

Prepared 2026-11-03 (election night). **Plan only — no code yet.** This revision **rejects the
replay/demo source as primary** and designs ingestion around **real election-result feeds**,
grounded in live probes run tonight.

```
   Polls ─► Aggregation ─► Forecast ─┐
                                     ├─► (NEW) Live Blend ─► Monte Carlo ─► Dashboard
   REAL Results ─► Snapshots ────────┘      by % reporting   (REUSED)
```

## 0. Determination — can real data realistically be obtained?
**Yes, but there is no free, uniform, real-time, machine-readable results source.** The realistic
options mirror the polling situation:
- **DDHQ Results API** is the right **primary** — live tonight, one API for all races, JSON, with
  official calls — **but it is gated behind enterprise OAuth credentials** (the $9.99 Pro does not
  include API access; a sales/enterprise arrangement is required).
- **State Secretary-of-State feeds** are the **free fallback** — real and official, but
  heterogeneous (a different system, host and format per state), with no uniform "call" signal,
  requiring ~8 bespoke, fragile adapters.
- **AP Elections API** is the newsroom gold standard but **paid-contract only** (not obtainable).

So: real data is obtainable, and the recommendation is **DDHQ primary (pending credentials) with a
per-state SoS fallback**. The decision gate is obtaining DDHQ Results API access.

## 1. Source evaluation (empirical, probed 2026-11-03)

| Source | Live tonight? | Machine-readable | Uniform (one adapter) | Official calls | Access / cost | Verdict |
|--------|:---:|:---:|:---:|:---:|---|---|
| **DDHQ Results API** (`resultsapi.decisiondeskhq.com`) | ✅ health 200, `last_updated` current | ✅ JSON | ✅ one API, all races | ✅ `/race-calls` | **OAuth enterprise (paid)** — `/races` → **401** | ✅ **Preferred primary** (if credentials) |
| **AP Elections API** (`api.ap.org`) | ✅ (newsroom standard) | ✅ JSON | ✅ | ✅ | **Paid contract** — → **403** | ❌ Inaccessible |
| **State SoS feeds** | ✅ (e.g., GA/NC/MN reachable) | ⚠️ varies | ❌ per-state | ❌ none standard | Free | ✅ **Free fallback** (high effort) |
| — NC (`dl.ncsbe.gov` ENRS) | ✅ | ⚠️ downloadable files behind an HTML portal | — | — | Free | Easiest SoS: dated result files |
| — GA (`results.sos.ga.gov`) | ✅ | ⚠️ SPA; data endpoint undocumented (`/api/*` → 404) | — | — | Free | Needs reverse-engineering |
| — TX | ✅ | ⚠️ different host (`results.sos.state.tx.us` doesn't resolve) | — | — | Free | Needs host discovery |
| **Google / news / Wikipedia** | display only / lags | ❌ no public API | — | — | — | ❌ Not a source |

**Key probe results:** DDHQ results endpoints return **401** (live but gated); AP returns **403**
(contract); SoS sites load but are **non-uniform** (NC = file portal, GA = SPA with hidden API, TX
= other host). There is no clean free uniform feed.

## 2. Technical feasibility (requirement #7)

| | DDHQ API | State SoS feeds | AP API |
|---|---|---|---|
| **Refresh frequency** | ~30–60 s on election night | 1–10 min per state (be polite; cache) | ~30–60 s |
| **Rate limits** | per plan (enterprise; generous) — honour `Retry-After` | none published → self-throttle, backoff, ETag/If-Modified | per contract |
| **Credentials** | **OAuth2 client id/secret (enterprise)** — required | none (public) | paid API key |
| **Integration effort** | **Low** — one adapter, JSON, documented (`/api/v4/race/{id}`, `/race-calls`, `/vote-history/races/{id}`) | **High** — ~8 bespoke adapters; mixed CSV/JSON/SPA; brittle | Low (if licensed) |
| **Feasibility verdict** | **High, if credentials obtained** | **Medium; fragile; realistic only for a subset of states** | **Not feasible** (cost) |

## 3. ResultsSource interface
Mirrors the Phase A `PollSource` so adapters are swappable with no downstream change:

```
class ResultsSource(ABC):
    name: str
    def fetch(self) -> list[ReportingSnapshot]: ...        # race-level roll-ups
    def fetch_detail(self) -> list[ElectionResult]: ...     # optional candidate/county detail
```

Selected by config (`EI_RESULTS__SOURCE = ddhq | sos`); a thin `ResultsIngestor`
validates/dedups/quarantines and writes via the repositories (reusing Phase-2 invariants).

## 4. Adapter designs

### 4a. DDHQ Results adapter (preferred)
- Auth: OAuth2 client-credentials → bearer (`POST /api/v4/oauth/token`).
- `GET /api/v4/races` (+ `/api/v4/race/{raceID}`) filtered to the 8 Senate battlegrounds → per-race
  vote totals, per-candidate votes, `percent_reporting`; `GET /api/v4/race-calls` → official calls;
  `/api/v4/vote-history/races/{race_id}` → the night's snapshot history (seeds `reporting_snapshots`).
- Map candidate → party (DDHQ provides party) → `dem_votes/rep_votes/other_votes`, `margin`,
  `leader_party`, `is_called`. One adapter covers everything.

### 4b. State SoS adapter set (free fallback)
- A small adapter per battleground implementing `ResultsSource`, registered in a table of
  `(state → endpoint, parser)`. Prefer states with downloadable structured files (NC-style); for SPA
  states (GA) capture the underlying JSON endpoint; discover per-state hosts (TX).
- Each parser yields the same normalized `ReportingSnapshot`. **No official call signal** → calls are
  inferred by a guardrail (large margin + high `% reporting`) or left uncalled.
- Explicitly partial: ship the states that are tractable first; degrade gracefully for the rest.

## 5. Data model & repositories (database changes)
- **Migration 0005** — extend `election_results` with `county_fips VARCHAR NULL`, `vote_share DOUBLE`,
  `percent_reporting DOUBLE`; create **`reporting_snapshots`** (append-only race-level history):
  `snapshot_id, race_id, reported_at, percent_reporting, total_votes, dem_votes, rep_votes,
  other_votes, margin, leader_party, is_called, called_party, source, ingested_at`.
- **Entities:** `ElectionResult` (extended) + `ReportingSnapshot` (new) — Pydantic, same style.
- **Repositories:** extend `ElectionResultRepository`; new `ReportingSnapshotRepository`
  (`latest_for_race`, `history`, idempotent upsert on `(race_id, source, reported_at)`); wire into
  `Database`. No change to `polls`, `state_forecasts`, or the simulation tables.

## 6. Poll-to-results transition engine (`live/`) — engines preserved
A pure blend (new `live/results_blend.py`), feeding the **unchanged** Monte Carlo engine:

```
w = percent_reporting / 100
if is_called:  live_mean = ±LARGE (winner);  live_sigma = tiny          # pinned
else:          live_mean  = (1-w)*poll_mean + w*counted_margin
               live_sigma = max((1-w)*poll_sigma, SIGMA_FLOOR)
```
- `w=0` → 100% polls; `w=1` → real results replace the forecast; uncertainty shrinks with the
  outstanding vote. Emits a `StateForecast(method="live_blend_v1")` — the exact type the Monte Carlo
  engine already consumes. `live/update_engine.py` blends all races and runs the engine as-is.
- *(Future: expected-vote/outstanding-ballot model and early→late cross-state learning — these live
  only in `live/`, never in the engines.)*

## 7. Senate probability updates
`update_engine.run_live_update(db)` → blend → **unchanged `MonteCarloEngine`** → a `simulation_run`
with `regime="live"` + result (D / R / tie, expected seats, seat histogram). Each new results
snapshot triggers a run, so probabilities recompute as results arrive.

## 8. Dashboard requirements (presentation only)
A new **Live Results** tab: Senate control tracker (live D/R/tie + sparkline over snapshots),
per-race **% reporting / vote totals / leader / call status**, and **forecast-vs-actual** (pre-election
poll margin vs counted margin). A per-race badge shows **"polls" vs "live (x% in)"**. Forecast tab
unchanged.

## 9. Validation / calibration
Post-election: forecast P(winner) vs actual called winner → reliability, Brier, log-loss (reuse
`calibration/metrics.py`) → `docs/POST_ELECTION_CALIBRATION.md`.

## 10. Deliverables
Architecture doc (this) · source evaluation (§1) · `ResultsSource` design (§3) · adapter designs
(§4) · database changes (§5) · dashboard requirements (§8) · and, at build time: entities, repos,
ingestion layer, update engine, dashboard tab, tests.

## 11. Decision gate & phasing
**Gate (external):** obtain **DDHQ Results API credentials** (same enterprise access as the polls
API). Outcomes:
- **Credentials obtained →** DDHQ primary adapter (clean, one adapter, real-time, official calls). *(Recommended.)*
- **No credentials →** build the **SoS fallback** for the tractable battlegrounds (free, high effort,
  partial coverage, no official calls), **or** decline real live data this cycle. The demo/replay
  source is retained **only** as an offline test fixture, never as the live source.

Phasing once the gate is resolved: **E1** data model + `ResultsSource` + chosen adapter →
**E2** blend/update engine + live Monte Carlo (the success criterion) → **E3** dashboard tab →
**E4** calibration.

## 12. Constraint guarantee
Poll aggregation, forecast, and Monte Carlo engines are **not rewritten**. Election-night logic is
additive: a new `ResultsSource` + adapters (`data/ingestion/results/`), a new blend/update layer
(`live/`), one migration, repository/dashboard additions, and calibration. The Monte Carlo engine is
reused verbatim — the live blend only feeds it `StateForecast` inputs derived from real results.
```
