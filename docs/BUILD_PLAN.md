# Finalized Build Plan
**2026 Senate Control Intelligence System**
Prepared: 2026-10-29 · Solo build · Supersedes the phase sequence in
[`docs/ARCHITECTURE_ROADMAP.md`](docs/ARCHITECTURE_ROADMAP.md) §11

> The roadmap remains authoritative on **architecture and methodology**. This document is
> authoritative on **build order, scope, and acceptance gates**, as a single linear sequence of
> 12 phases. No code is written until the pre-coding gate (Section C) is cleared.
> Election Day is **2026-11-03** — four build days remain (Oct 29 – Nov 1).

---

## A. Architecture review (before implementing anything)

### A.1 Unnecessary complexity (cut or simplify for a solo build)

| Item | Verdict | Action |
|---|---|---|
| **Full Shapley attribution** (averaging over all swap orders) | Over-engineered — `n!` orders for ~10 Tier-1 states | Use **single-pass sequential swap** (one order), or sampled permutations only if sums drift. Contributions still sum to the move. |
| **Dual independent result feeds + reconciliation** | Ideal, not essential for v1 | **One primary feed + manual SoS spot-checks** (already the spec's cut). Keep the quarantine rules; drop cross-feed diffing from the critical path. |
| **Multi-factor demographic error** (several `η` factors + loadings) | Loadings are hard to source cleanly in days | Ship **one national factor + one demographic axis** (e.g. non-college-white); widen thin states by hand. Expand later. |
| **Cross-state live learning** (early states → late-state priors) | Elegant but a correctness/time risk under pressure | **Defer to stretch.** Per-state live projection first; add cross-state only if replay is green with time to spare. |
| **LLM news/event triage** | Not on the numeric path; pure nice-to-have | **Drop for v1.** Event flags entered manually if needed. |
| **MCP server, House module, per-source attribution, expected-info-gain** | All explicitly optional in the roadmap | Build **last**; allowed to ship absent. |
| **Hierarchical Stan/PyMC pooling** | Already cut in the roadmap | Stays out of v1. |

**Net:** the methodology is sound; the risk is building *all* of it. The cuts above are
pre-decided so they are not improvised at 1 am.

### A.2 Missing components (add to the plan)

1. **Reference-data acquisition is an unscoped iceberg.** Races, candidates, counting rules,
   2024 county results *by vote method*, ACS demographics, **pollster grades & house effects**,
   **poll-close times per state**, recount bands, the Senate **holdover roster**, and 2026 House
   lines must all be sourced and loaded. This is likely the single largest time cost and is now
   **Phase 3's explicit deliverable** — and should start **in parallel on day one** (long pole).
2. **Poll-close clock / resolution calendar.** Freezing inputs at each state's close, switching
   regimes, and flagging seats that legitimately resolve after Nov 8 (GA runoff, ME RCV, AK mail)
   all need a **reference table of close times + resolution rules**. Not currently a first-class entity.
3. **Feed credentials in config.** `config/settings.py` models only the Claude key. Add typed,
   env-only settings for the results-feed API key(s) and the Slack webhook.
4. **Dev fixtures before real data.** A small synthetic "golden path" dataset so Phases 4–6 can
   be built and tested *before* real feeds/archives arrive.
5. **Natural idempotency key at ingest** (`unit + source + source_ts`) so replayed/re-fetched
   snapshots dedupe deterministically.

### A.3 Risks for a solo developer

| Risk | Severity | Mitigation |
|---|---|---|
| Time goes to modelling; **data prep starves** | 🔴 | Start reference-data acquisition on day one, in parallel; timebox modelling |
| **No second pair of eyes** | 🔴 | Replay + property tests are the safety net — build them **early (Phases 6–7), not last** |
| **Feed license/access unresolved** | 🔴 | Gating item in the pre-coding gate; design against recorded fixtures regardless |
| **Vote-method not reported live** by many states | 🔴 | The outstanding-ballot model depends on live method granularity — **validate per Tier-1 state before building Phase 9** |
| Ops unfamiliarity (systemd/tmux/backups) | 🟡 | Keep deployment dead simple; rehearse once in Phase 12; laptop standby as fallback |
| Calibration overfit on 3 cycles / 1am burnout | 🟡 | Literature priors over fitting; determinism reduces debugging pain |
| **12 phases in 4 days** | 🔴 | Pre-decided scope cuts (A.1); protect non-negotiables; phases are time-boxed |

### A.4 Assumptions to validate *before* coding

1. **Results-feed access & license** confirmed for intended use. *(Gating.)*
2. **Archived 2022 snapshots** exist in usable form — county-level, or state-level fallback, or synthetic. *(Sets the calibration floor.)*
3. **Live vote-method granularity** is actually exposed by the Tier-1 feeds. *(The whole outstanding-ballot model hinges on this.)*
4. **Reference data is obtainable** in days: pollster grades/house effects, poll-close times, 2024 county results by method, ACS demographics, holdover roster, 2026 House lines.
5. **DuckDB read-only-while-writing** behaves acceptably for the reader processes. *(Validate empirically in Phase 2.)*
6. **Claude API budget** sufficient for election-night narration volume.
7. **Deployment target** (VM + credentials) is available before Nov 2.

> If 1, 2, or 3 fail, the scope changes materially — resolve them first (Section C gate).

---

## B. The 12-phase build plan

> Effort = **ideal focused dev-days** (one developer, uninterrupted) + risk flag. Calendar is the
> compressed solo schedule. "Cut if behind" states the pre-decided descope.

### Phase 1 — Project Foundation
- **Objective:** a runnable, tested skeleton with all contracts and configuration in place.
- **Deliverables:** scaffold (done) extended — typed feed/Slack secrets in `config`; verified
  logging; `exceptions`; `cli` command stubs (`info`, `run`, `backtest`, `replay`); test markers;
  `tests/fixtures/` with a synthetic golden-path dataset; CI running `unit` + `integration`.
- **Dependencies:** none.
- **Validation:** `pytest -m unit` green; `election-intelligence info` prints resolved config;
  byte-compile/lint/type-check clean.
- **Estimated effort:** ~0.5 day (mostly complete) · 🟢

### Phase 2 — Database Layer
- **Objective:** the DuckDB schema and reproducibility model — the data spine.
- **Deliverables:** `data/storage/schema.sql` (reference, append-only inputs, runs & outputs per
  roadmap §5); `scripts/init_db.py`; `repository.py` with invariants (totals-decrease rejection,
  110%-turnout quarantine, atomic per-run writes, read-only reader connections); `runs` table with
  `inputs_hash` / `seed` / `code_version`; `backup.py` (15-min backup + Parquet reader snapshot).
- **Dependencies:** Phase 1.
- **Validation:** schema creates cleanly; invariant tests green; a dummy run writes atomically and
  reproduces from `(inputs_hash, seed, code_version)`; reader opens read-only while writer holds the file.
- **Estimated effort:** ~1.0 day · 🟡

### Phase 3 — Polling Data Model
- **Objective:** canonical entities + loaders for polls *and all reference data* (the iceberg).
- **Deliverables:** loaders/seeders for `races`, `candidates`, `reporting_units` (+ 2024 votes by
  method, demographics), `fundamentals`, **pollster grades/house effects**, **poll-close & resolution
  calendar**, recount bands, `senate_holdovers`; `polls` ingestion with schema validation; natural
  idempotency key at ingest.
- **Dependencies:** Phase 2; **assumption A.4(4) resolved**. *Start data acquisition day one, in parallel.*
- **Validation:** a real (or best-available) poll set loads and validates; reference tables populated
  and spot-checked against official sources; holdover count matches the official roster.
- **Estimated effort:** ~1.0 day build + **ongoing data acquisition** · 🔴 (data availability)

### Phase 4 — Poll Aggregation Engine
- **Objective:** per-state polling average with weighting, house-effect removal, and decay.
- **Deliverables:** `forecast/polls.py` — weight `w = q·min(√n,cap)·e^(−λ·age)·ρ_LV`, house-effect
  subtraction, single-pollster cap (~25%), 7–10 day half-life → `(mu_poll, sigma_poll)` per state.
- **Dependencies:** Phase 3.
- **Validation:** unit tests on each weight factor; golden-fixture reproduction; sanity-check
  averages against a published aggregate for a few states.
- **Estimated effort:** ~0.75 day · 🟡

### Phase 5 — Senate Forecast Engine
- **Objective:** combine polls + fundamentals into a per-state margin distribution with named drivers.
- **Deliverables:** `forecast/fundamentals.py` (regression prior); `forecast/blend.py` (precision-
  weighted Bayesian posterior); `forecast/specials.py` (RCV for ME/AK, GA 50%+1, independents/caucus);
  `StateForecast(mu_margin, sigma_margin, p_win, drivers[])`. Pooling = documented stub.
- **Dependencies:** Phase 4.
- **Validation:** blend-math unit tests; thin-poll state → fundamentals-dominant check; specials
  produce the extra outputs (`P(>50%)`, RCV first-round+transfer); 80% margin-interval coverage sane vs 2022.
- **Estimated effort:** ~1.0 day · 🟡

### Phase 6 — Correlated Monte Carlo Simulator
- **Objective:** turn per-state margins into chamber-control probabilities. *(First headline number.)*
- **Deliverables:** `simulate/correlation.py` (factor structure `M_s = μ_s + ε_nat + βₛ·η + ε_s`,
  Student-t national term), `engine.py` (vectorised, seed = run_id, 50k–100k draws), `outcomes.py`
  (seat counting, holdovers from table, R≥50 / D≥51 control, GA/RCV handling), `paths.py`,
  `conditionals.py`.
- **Dependencies:** Phase 5.
- **Validation:** property tests (correlation PSD, seat sums, `P∈[0,1]`, monotonicity); MC stderr
  < 0.3 pt at 100k; **reproducibility** (same seed → identical outputs); **control probability prints end to end.**
- **Estimated effort:** ~1.0 day · 🟡
- **Milestone:** end of Phases 5–6 = the spec's "a control probability prints."

### Phase 7 — Historical Replay Framework
- **Objective:** replay a past election night end to end; prove resume-after-crash.
- **Deliverables:** `scripts/replay_night.py`; `calibration/replay.py`; snapshot-replay through the
  (forthcoming) live path and the simulator; fixtures under `tests/replay/`; 1× and 5× speeds.
- **Dependencies:** Phase 6; **assumption A.4(2) resolved**. (Live engine arrives in Phase 9; replay
  harness is built now against recorded snapshots and wired to the live path when it lands.)
- **Validation:** a 2022 (or state-level fallback) night replays with **no manual intervention**;
  kill mid-replay → clean resume from DuckDB; deterministic re-run.
- **Estimated effort:** ~1.0 day · 🔴 (archived-data dependent)

### Phase 8 — Calibration Framework
- **Objective:** measure whether the forecast is honest (reliability, coverage).
- **Deliverables:** `calibration/metrics.py` (Brier, log-loss, reliability curve, interval coverage,
  sharpness); `scripts/run_backtest.py`; acceptance-gate report.
- **Dependencies:** Phases 6–7.
- **Validation (floor):** 80% interval coverage **75–85%** on the 2022 check; reliability not
  catastrophically off; reproducibility green. *Multi-cycle (2014/2018/2022) = stretch.*
- **Estimated effort:** ~0.75 day (floor) · 🟡

### Phase 9 — Election Night Engine
- **Objective:** the live regime — ingest results, project live, run the same simulator, and drive
  ratings/attribution/alerts. *(Largest phase.)*
- **Deliverables:** `data/ingestion/adapters/` (one feed) + `reconciliation.py` (quarantine, idempotency,
  lag); `live/` (`county_projection`, `swing`, `prior_fade` `α=(1−pct_in)^k`, `guardrails`: max move/snapshot,
  call P=0.995, stale widening, recount band); `worker/` (`scheduler` event-driven + 30s debounce + 2-min
  backstop, `pipeline` 5 steps, `run` one atomic `runs` row); `ratings/` (labels, hysteresis, leverage);
  `attribution/` (single-pass sequential swap); `alerts/` (rules P1–P3/Info, dedup, Slack); **stale-worker P1 alarm**.
- **Dependencies:** Phases 6–7; **assumption A.4(1,3) resolved**.
- **Validation:** live replay through the engine is clean; guardrails fire correctly; garbage feed
  quarantined + alerted; stale feed widens (not holds); attribution contributions sum to the move;
  alert volume under the agreed per-hour cap; kill/resume clean.
- **Estimated effort:** ~2.0 days · 🔴
- **Cut if behind:** county model for **Tier-1 states only**, state-level elsewhere; cross-state
  learning deferred; attribution by state only.

### Phase 10 — Streamlit Dashboard
- **Objective:** a read-only operator view of the live model.
- **Deliverables:** `dashboard/panels/` — control gauge (+ sparkline), seat histogram, Tier-1 board
  (margin, % in, outstanding method, label, leverage, feed health), path tracker, change log (last 20
  narrated moves), data-health panel. Opens DuckDB **read-only**.
- **Dependencies:** Phase 9 (runs + outputs to display).
- **Validation:** Playwright smoke test — panels render, no console errors, update on a new run;
  confirmed read-only (never writes).
- **Estimated effort:** ~1.0 day · 🟡

### Phase 11 — Narrative Layer
- **Objective:** constrained plain-English explanation of each move, provably faithful to the numbers.
- **Deliverables:** `narrative/templates.py` (structured → skeleton), `narrative/generate.py` (single
  constrained Claude call via `llm/` client, record-only input), `narrative/validator.py` **(hard gate:
  every numeric token must match the attribution record; certainty-word filter; one retry then suppress)**;
  suppression of sub-2-point moves unless a label changed; symmetric wording for both parties.
- **Dependencies:** Phase 9 (attribution record).
- **Validation:** planted wrong number is **rejected**; "will win" / certainty words trip the filter;
  every output number traces to the record; wording symmetric across parties.
- **Estimated effort:** ~0.5 day · 🟡

### Phase 12 — Deployment
- **Objective:** run reliably through Nov 2–8 with recovery paths.
- **Deliverables:** worker + dashboard on a 1 vCPU / 2 GB VM under `systemd` restart in `tmux`;
  15-min DuckDB backup to object storage; `docs/runbook.md`; `docs/break_glass.md` (pin a state,
  mute a feed, restart, failover); laptop cold standby with code + DB copy.
- **Dependencies:** a green freeze of Phases 1–11; **assumption A.4(7) resolved**.
- **Validation (pre-flight):** replay a 2022 night unaided; kill worker mid-replay → clean resume;
  garbage feed → quarantine + alert; validator rejects a planted number; backup/restore rehearsed;
  **results-feed license confirmed**.
- **Estimated effort:** ~0.5 day setup + continuous operation · 🟡

---

## C. Sequencing, effort, and the pre-coding gate

### C.1 Effort summary

| Phase | Ideal days | Risk |
|---|---|---|
| 1 Foundation | 0.5 | 🟢 |
| 2 Database | 1.0 | 🟡 |
| 3 Polling data model (+ data acquisition) | 1.0 + ongoing | 🔴 |
| 4 Poll aggregation | 0.75 | 🟡 |
| 5 Forecast engine | 1.0 | 🟡 |
| 6 Monte Carlo | 1.0 | 🟡 |
| 7 Replay framework | 1.0 | 🔴 |
| 8 Calibration | 0.75 | 🟡 |
| 9 Election-night engine | 2.0 | 🔴 |
| 10 Dashboard | 1.0 | 🟡 |
| 11 Narrative | 0.5 | 🟡 |
| 12 Deployment | 0.5 | 🟡 |
| **Total** | **~11 ideal dev-days** | — |

### C.2 The honest gap

~11 ideal dev-days are being compressed into **~4 calendar days**. This is survivable only with
the pre-decided cuts in A.1 and the per-phase "cut if behind." **Protect the non-negotiables:**
correlated Monte Carlo (6), the outstanding-ballot vote-method model (9), stale-feed widening (9),
and the replay test (7). Let these fall first, in order: House → MCP → per-source attribution →
cross-state learning → multi-cycle calibration → multi-factor demographics.

### C.3 Parallelism for a solo dev

- **Day one, in the background:** reference-data acquisition (Phase 3) and resolving the three
  gating assumptions. Data is the long pole; start it before the fun modelling work.
- **Build fixtures first** so Phases 4–6 proceed without waiting on real data.
- **Replay + property tests early** (Phases 6–7) — they are your only reviewer.

### C.4 Pre-coding gate (must clear before Phase 2 implementation)

1. ☐ Results-feed access & license confirmed (A.4-1)
2. ☐ Archived 2022 snapshot availability decided — county / state / synthetic (A.4-2)
3. ☐ Live vote-method granularity confirmed per Tier-1 state (A.4-3)
4. ☐ Reference-data sources identified and reachable (A.4-4)
5. ☐ Deployment target + credentials secured (A.4-7)

Phase 1 (foundation) may proceed now, as it depends on none of these. Phases 2+ wait on the gate.
