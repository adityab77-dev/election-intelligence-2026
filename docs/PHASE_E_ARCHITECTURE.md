# Phase E — Election-Night Results Engine (Architecture Plan)

Prepared 2026-11-03. **Plan only — no code yet.** Transforms the platform from a
poll-based forecaster into a live engine that transitions from polls to real vote
counts as results arrive.

```
   Polls ─► Aggregation ─► Forecast ─┐
                                     ├─► (NEW) Live Blend ─► Monte Carlo ─► Dashboard
   Live Results ─► Snapshots ────────┘        by % reporting   (REUSED)
```

## 1. Design principles (constraint-driven)
- **Reuse, don't rewrite.** The Monte Carlo engine is used **as-is** — it already takes a
  list of `StateForecast(mean, sigma)`. Election-night logic only *changes the per-state
  inputs* it receives. The poll aggregation and forecast engines are untouched.
- **New logic lives in the existing stubs:** `live/` (the blend / update engine) and a new
  `data/ingestion/results/` (results sources), plus `calibration/` for post-election scoring.
- **Pluggable results source**, mirroring the Phase A `PollSource` pattern, so a real feed
  (DDHQ/AP/SoS) can replace the demo source with no downstream change.
- **Append-only history** of reporting snapshots → the control tracker, replay, and
  calibration all read from it.

## 2. Data model

### ElectionResult (extend the existing Phase 2 table/entity)
`election_results` already stores `race_id, candidate_id, votes, pct_expected_vote, is_called,
source, reported_at, quarantined, ingested_at`. **Migration 0005** adds the requested fields:
`county_fips VARCHAR NULL`, `vote_share DOUBLE`, `percent_reporting DOUBLE`. One row per
(race, [county], candidate, snapshot) — the raw reported votes.

### ReportingSnapshot (new)
A race-level roll-up captured each time results update — **append-only** so we keep the night's
history. **Migration 0005** also creates `reporting_snapshots`:

| Column | Notes |
|---|---|
| `snapshot_id` PK | |
| `race_id` FK → senate_races | |
| `reported_at` TIMESTAMPTZ | source time of this snapshot |
| `percent_reporting` DOUBLE | 0–100 |
| `total_votes`, `dem_votes`, `rep_votes`, `other_votes` BIGINT | |
| `margin` DOUBLE | counted D − R, points |
| `leader_party` VARCHAR, `is_called` BOOLEAN, `called_party` VARCHAR NULL | |
| `source` VARCHAR, `ingested_at` TIMESTAMPTZ | |

Entities: `ElectionResult` (extended) and `ReportingSnapshot` (new) — Pydantic models, same
style as the rest. No change to `polls`, `state_forecasts`, or the simulation tables.

## 3. Repositories
- Extend `ElectionResultRepository` (exists) with `latest_for_race`, `list_by_race`.
- New `ReportingSnapshotRepository`: `latest_for_race(race_id)`, `history(race_id)`,
  idempotent upsert keyed by `(race_id, source, reported_at)`.
- Wire both into the `Database` facade.

## 4. Results ingestion layer (`data/ingestion/results/`)
- `ResultsSource` interface: `fetch() -> list[ReportingSnapshot]` (+ optional per-candidate
  `ElectionResult`s), mirroring `PollSource`.
- **V1 adapter — `ReplayResultsSource` (demo):** deterministically advances `percent_reporting`
  over time and converges each race's counted margin toward a configured "election-night truth"
  (seeded from the current poll margin, with a sampled polling-miss so results differ from polls).
  This lets the dashboard *demonstrate* the poll→results transition with no paid feed.
- **Future adapters (pluggable, same interface):** DDHQ race endpoint (if licensed), state SoS
  scrapers, or a recorded 2022/2024 replay. No downstream change to swap them in.
- **Validation / dedup / quarantine (reuse Phase-2 invariants):** reject snapshots where votes
  decrease without a correction, `percent_reporting` outside 0–100, or a county exceeds plausible
  turnout; dedup on the natural key; stale-feed handling widens uncertainty rather than freezing.

## 5. Forecast transition / update engine (`live/`)
`live/results_blend.py` — the heart of Phase E, a pure function:

```
w = percent_reporting / 100                     # results weight
if snapshot.is_called:
    live_mean  = ±LARGE in the called party's direction   # pinned
    live_sigma = tiny
else:
    live_mean  = (1 - w) * poll_mean   + w * counted_margin
    live_sigma = max((1 - w) * poll_sigma, SIGMA_FLOOR)
```

- `w = 0` (polls not closed) → **100% polling forecast** (unchanged).
- `w = 0.1 / 0.5 / 0.9` → **90/10, 50/50, 10/90** poll-vs-results blend, exactly as specified.
- `w = 1.0` → **counted margin replaces the forecast**, sigma at the floor (actual outcome).
- Uncertainty shrinks with the outstanding vote; called races are pinned near-certain.

The blend emits a `StateForecast(mean, sigma, method="live_blend_v1")` — **the exact type the
Monte Carlo engine already consumes**. `live/update_engine.py` builds one blended forecast per
race (poll-only where no results exist) and hands the list to the **unchanged** `MonteCarloEngine`.

> V1 blends the *counted* margin linearly, per the stated example. The richer expected-vote /
> outstanding-ballot model (from `PROJECT_SPEC.md`) and early→late cross-state learning are
> noted as future upgrades; they would change only the `live/` blend, not the engines.

## 6. Senate probability updates
A **live run** = `update_engine.run_live_update(db)`: blend all races → `MonteCarloEngine` →
`SimulationOutput` stored as a `simulation_run` with `regime = "live"` plus its result
(D / R / tie probabilities, expected seats, seat histogram — all already produced). Each new
results snapshot triggers a new live run, so **D / R / tie recompute whenever results arrive**.
Correlation still applies across the still-polling states via the engine's shared national error.

## 7. Dashboard enhancements (presentation only)
A new **"Live Results"** tab (3rd tab), reading `reporting_snapshots` + the latest `regime="live"`
run:
- **Senate control tracker** — live D / R / tie with a sparkline over the night's snapshots.
- Per-race rows: **% reporting**, **current vote totals** (D/R), leader, **call status**.
- **Forecast vs Actual** — for called/mature races, the pre-election poll margin vs the counted
  margin, and whether the forecast favorite is winning.
- The existing Forecast tab is unchanged; a small banner indicates "polls" vs "live" mode per race.

## 8. Validation / calibration (`calibration/`)
Post-election: for each race, compare the **pre-election forecast P(winner)** to the **actual
called winner** → reliability curve, Brier score, log-loss (reuse `calibration/metrics.py`).
Produce `docs/POST_ELECTION_CALIBRATION.md`. Interval-coverage of the 80% margin band vs actual
margins is also reported.

## 9. CLI & scheduling
- `ingest-results [--source replay|…]` — pull the latest snapshot(s) into the tables.
- `live-update` — blend + Monte Carlo + store a `regime="live"` run.
- `refresh-results` — ingest **then** update (one command for the loop).
- **Automation:** on election night, run `refresh-results` on a short interval (reuse the
  Phase-C GitHub Action / Task Scheduler pattern); each run re-computes and the dashboard follows.

## 10. Deliverables
1. `ElectionResult` (extended) + `ReportingSnapshot` entities; **migration 0005**.
2. `ReportingSnapshotRepository` + extended `ElectionResultRepository`; `Database` wiring.
3. `data/ingestion/results/` — `ResultsSource` interface + `ReplayResultsSource` + normalizer.
4. `live/results_blend.py` (blend) + `live/update_engine.py` (update engine); MC reused.
5. Dashboard **Live Results tab** + per-race mode indicator.
6. `calibration` forecast-vs-actual report.
7. Tests — blend math (unit), ingestion + dedup (integration), end-to-end replay that shows the
   control probability shifting from poll-based to vote-based, calibration.

## 11. Phasing
- **E1 — Data & ingestion:** migration 0005, entities, repos, `ResultsSource` + replay adapter, tests.
- **E2 — Update engine:** blend + `run_live_update` (live MC run), end-to-end replay test proving
  the transition (the success criterion).
- **E3 — Dashboard:** Live Results tab + control tracker + forecast-vs-actual.
- **E4 — Validation:** post-election calibration report.

## 12. Constraint guarantee
The **poll aggregation, forecast, and Monte Carlo engines are not rewritten.** Election-night
logic is additive: new ingestion (`data/ingestion/results/`), a new blend/update layer (`live/`),
one migration, repository/dashboard additions, and calibration. The Monte Carlo engine is reused
verbatim — the live blend simply feeds it `StateForecast` inputs derived from results.

## 13. Risks & open questions
1. **No free live results feed** (AP/DDHQ paid; SoS heterogeneous; Wikipedia lags). V1 uses the
   **replay/demo source** to prove the mechanism; a real adapter is a drop-in later. *(Biggest item.)*
2. **Blend simplicity** — linear counted-margin blend can misread late-counting "blue/red shift";
   the expected-vote model is the future fix (lives only in `live/`).
3. **Calls** — V1 trusts the feed's `is_called`; a model-based call (margin + % in + guardrails)
   is a later enhancement.
4. **Cross-state learning** (early states informing late ones) is deferred; the engine's shared
   national error provides baseline correlation.

## 14. Success-criteria mapping
*"The dashboard automatically shifts from poll-based forecasting to vote-based forecasting as
results arrive."* → delivered by the **E2 update engine** (blend weight `w = % reporting`, feeding
the unchanged Monte Carlo) and the **E3 Live Results tab**; the **E2 replay end-to-end test** proves
the shift (0% reporting = poll forecast → 100% = actual outcome).
