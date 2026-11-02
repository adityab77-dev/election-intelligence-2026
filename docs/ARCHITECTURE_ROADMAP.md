# Architecture Review & Implementation Roadmap
**2026 Senate Control Intelligence System**
Prepared: 2026-10-28 · Principal engineer review of `PROJECT_SPEC.md` · Status: pre-implementation

> This document governs all future development. It does **not** contain forecasting code.
> It assesses the proposed architecture, fixes gaps, and sequences the build into
> validated phases. Where it differs from `PROJECT_SPEC.md`, the spec remains the
> authority on *methodology*; this document is the authority on *construction order,
> structure, and acceptance gates*.

---

## 0. The constraint that shapes everything

Today is **2026-10-28**. Election Day is **2026-11-03**. The spec allocates four build
days (Oct 29 – Nov 1) for a solo developer, then a live operating window (Nov 2 – 8).

Every recommendation below is filtered through that reality. The governing rule:

> **Build the "keep no matter what" core first, and let it degrade gracefully.
> Everything else is optional scope that must not block a runnable system each night.**

The spec's own non-negotiables — *correlated Monte Carlo, the vote-method model for
outstanding ballots, stale-feed widening, and the replay test* — are the spine of the
roadmap. Features that are intellectually central but schedule-hostile (multi-cycle
calibration, hierarchical Bayesian pooling, county models for all states) are explicitly
scoped as **stretch** and given literature-prior fallbacks so their absence never stops a nightly run.

---

## 1. Architecture assessment

### 1.1 Verdict on the proposed design

**Endorsed, with reservations.** The core decision — one deterministic Python worker as
the *sole writer*, with the dashboard and optional MCP server as *read-only* consumers of a
single DuckDB file — is the correct architecture for a one-person, one-week, high-stakes build.
It is right for the following concrete reasons:

- **Determinism is a correctness requirement, not a preference.** Any number that may be
  quoted publicly must be reproducible from `(inputs_hash, seed, code_version)`. Keeping
  LLMs entirely out of the numeric path is the single most important design choice in the spec.
- **One writer eliminates the hardest class of bugs** (concurrent-write races, lock
  contention) for free. DuckDB is single-process-writer by nature; the architecture leans
  into that constraint instead of fighting it.
- **The reader/writer split means a dashboard or MCP crash cannot corrupt the forecast.**
  Failure is contained to the thing that failed.
- **The "run = one row" model** (inputs hash + seed per run) gives replay, attribution, and
  audit essentially for free, because reproducibility is baked into the data model rather
  than bolted on.

### 1.2 Strengths to preserve

| Strength | Why it matters |
|---|---|
| Correlation modelled as a factor structure, not state independence | The #1 way election models go overconfident; the spec treats it as *the* model, correctly |
| Two regimes, one Monte Carlo engine | Pre-election and live share the simulator; outputs can never disagree across screens |
| Prior fades with *vote completeness*, not clock time | Robust to slow-counting states (CA, AK); avoids the classic "lead evaporates overnight" error |
| Explainability via swap-based attribution | Makes the narrative layer honest-by-construction; contributions sum to the move |
| Append-only snapshots | Full replay and point-in-time rebuild; no destructive updates |

### 1.3 Risks and gaps (ranked)

1. **Calibration data availability (critical, schedule).** The spec assumes "archived 2022
   election-night county snapshots" exist and are clean. **Acquiring and normalising
   point-in-time county data for even one past night is itself a multi-day task** and is the
   most likely thing to blow the timeline. *Mitigation:* treat a single 2022 replay as the
   bar; fall back to **literature priors** (3–5 pt national miss, t-dof≈5) for the
   simulation's error structure rather than fitting them from scratch. Multi-cycle backtesting
   (2014/2018/2022) is **stretch**.

2. **Live results feed access & licensing (critical, external).** AP Elections API / DDHQ are
   paid and licensed; SoS pages are scrapeable but heterogeneous and fragile. The system is
   worthless with no result feed. *Mitigation:* confirm feed access **first** (pre-flight
   checklist item already in spec); design the results adapter against a **recorded fixture**
   so the pipeline is testable without live access; keep a manual-entry path.

3. **Single-writer is also a single point of failure.** If the worker dies and does not
   restart, the forecast freezes silently. *Mitigation:* systemd restart, 15-min DuckDB
   backup to object storage, a laptop cold standby with the same code + DB copy, and a
   **stale-run alarm** (dashboard shows "last successful run age"; P1 if > N minutes during counting).

4. **DuckDB concurrency nuance.** Readers (dashboard, MCP) opening the *same file* the writer
   holds can hit lock/consistency edges. *Mitigation:* writer owns a read-write connection;
   readers open **read-only**; consider the writer checkpointing to a Parquet/DuckDB snapshot
   the readers consume, decoupling reader load from writer locks. Validate this early (Phase 0).

5. **Narrative hallucination risk.** Even constrained, an LLM can emit numbers not in the
   record. *Mitigation:* the validator is **not optional** — it is a hard gate; every numeric
   token in the output must match the attribution record or the text is rejected and retried
   once, then suppressed.

6. **Scope creep via the House module and MCP.** Both are genuinely useful and both are
   explicitly *lightweight / optional* in the spec. *Mitigation:* they are the **last** things
   built and are allowed to ship absent.

### 1.4 Changes I recommend to the spec

- **Promote "last successful run age" to a first-class P1 alert condition.** The spec covers
  stale *feeds* but not a stale *worker*; a frozen worker is the quietest and worst failure.
- **Make the reader snapshot (Parquet/DuckDB export) explicit**, not implied, to de-risk the
  concurrency edge in 1.4(4).
- **Add a `code_version` (git SHA) column to `runs`.** Reproducibility needs the code, not
  just inputs + seed.
- **Treat hierarchical pooling (spec Forecast Step 4, Stan/PyMC) as out-of-scope for v1.**
  The spec's own "solo replacement" table already cuts it; the roadmap honours that cut and
  substitutes fixed demographic-factor loadings + hand-widened variance for thin states.

---

## 2. Development roadmap (high level)

```
Phase 0  Foundation & data contracts      ── schema, run model, replay harness, feed interface
Phase 1  Pre-election forecast + MC core  ── blend → correlated simulation → control probability
Phase 2  Live engine + results + replay   ── county projection, swing, prior fade, 2022 replay
Phase 3  Dashboard + alerts + attribution ── read-only UI, Slack, swap-based drivers
Phase 4  Narrative + House + MCP + freeze  ── constrained LLM prose, lightweight House, optional MCP
Phase 5  Operate (Nov 2–8)                ── run, monitor, back up, break-glass
```

Each phase **must end with something runnable**. Calibration is not a phase; it is a
continuous activity woven through Phases 1–2 with its own acceptance gates (Section 6).

Dependency spine: `0 → 1 → 2 → 3`, with `4` depending on `3` (narrative needs attribution,
House is independent and can slip), and `5` depending on everything surviving the Phase-4 freeze.

---

## 3. Recommended repository structure

The existing scaffold (`src/election_intelligence/` with `config`, `utils`, `data/ingestion`,
`data/storage`, `models`, `llm`, `analysis`, `dashboard`) is a correct foundation. Below is
the target layout; **bold** entries are new relative to the scaffold.

```
election-intelligence-2026/
├── docs/
│   ├── ARCHITECTURE_ROADMAP.md        # this document
│   ├── PROJECT_SPEC.md → (currently at repo root)
│   ├── runbook.md                     # operating runbook (Nov 2–8)
│   └── break_glass.md                 # pin a state, mute a feed, restart, failover
├── scripts/
│   ├── init_db.py                     # create schema from schema.sql
│   ├── load_reference_data.py         # races, units, demographics, 2026 House lines
│   ├── run_backtest.py                # offline calibration driver
│   ├── replay_night.py                # replay archived snapshots at 1× / 5×
│   └── export_parquet.py              # nightly warehouse export + reader snapshot
├── src/election_intelligence/
│   ├── config/                        # (exists) typed settings
│   ├── utils/                         # (exists) logging + shared helpers
│   ├── exceptions.py                  # (exists)
│   ├── cli.py                         # (exists) extend with worker/backtest/replay commands
│   ├── data/
│   │   ├── ingestion/
│   │   │   ├── base.py                # (exists) DataSource contract
│   │   │   ├── **adapters/**          # results_ap, results_ddhq, sos_scraper, polls,
│   │   │   │                          #   fundamentals, markets, news  (one file per source)
│   │   │   └── **reconciliation.py**  # dual-feed rules, quarantine, idempotency, lag
│   │   └── storage/
│   │       ├── duckdb_client.py       # (exists) connection wrapper
│   │       ├── **schema.sql**         # canonical DDL (Section 5)
│   │       ├── **repository.py**      # typed read/write; readers use read-only conns
│   │       └── **backup.py**          # 15-min backup + Parquet reader snapshot
│   ├── models/                        # (exists) abstract estimator base, reused below
│   ├── **forecast/**                  # PRE-ELECTION regime (deterministic)
│   │   ├── polls.py                   # weighting, house-effect removal, decay
│   │   ├── fundamentals.py            # regression prior
│   │   ├── blend.py                   # Bayesian precision-weighted posterior
│   │   ├── specials.py                # RCV (ME/AK), GA 50%+1, independents/caucus
│   │   └── pooling.py                 # STRETCH: hierarchical pooling (stub in v1)
│   ├── **live/**                      # ELECTION-NIGHT regime (deterministic)
│   │   ├── county_projection.py       # counted + predicted-outstanding blend by method
│   │   ├── swing.py                   # swing-vs-2024 regression on demographics ("needle")
│   │   ├── cross_state.py             # early-state national swing → late-state priors
│   │   ├── prior_fade.py              # α = (1 − pct_expected_in)^k
│   │   └── guardrails.py              # max move/snapshot, call P=0.995, stale widening, recount band
│   ├── **simulate/**                  # SHARED Monte Carlo engine (both regimes)
│   │   ├── correlation.py             # factor structure, loadings, covariance
│   │   ├── engine.py                  # vectorised draws; seed = run_id
│   │   ├── outcomes.py                # seat counting, control rule (R≥50 / D≥51), holdovers
│   │   ├── paths.py                   # top seat combinations by majority
│   │   └── conditionals.py            # P(control | party wins state s)
│   ├── **ratings/**
│   │   ├── labels.py                  # Toss-up/Lean/Likely/Safe/Projected thresholds
│   │   ├── hysteresis.py              # enter/exit bands + persistence rule
│   │   └── leverage.py                # control leverage, tipping-point, criticality, info gain
│   ├── **attribution/**
│   │   └── shapley.py                 # swap-order-averaged per-state / per-source contributions
│   ├── **narrative/**
│   │   ├── templates.py               # structured → prose skeleton
│   │   ├── generate.py                # single constrained Claude call (uses llm/ client)
│   │   └── validator.py               # number-match + certainty-word filter (HARD GATE)
│   ├── **alerts/**
│   │   ├── rules.py                   # P1/P2/P3/Info trigger logic
│   │   ├── dedup.py                   # 10-min dedupe, batching, 2-run confirmation
│   │   └── slack.py                   # Slack + phone-push delivery
│   ├── **worker/**
│   │   ├── scheduler.py               # APScheduler: event-driven + debounce + backstop
│   │   ├── pipeline.py                # the 5 steps: fetch → project → simulate → compare → alert
│   │   └── run.py                     # one tick = one `runs` row; writes all outputs atomically
│   ├── **calibration/**
│   │   ├── metrics.py                 # Brier, log-loss, reliability, interval coverage
│   │   ├── backtest.py                # point-in-time evaluation harness
│   │   └── replay.py                  # archived-night replay through the live engine
│   ├── llm/                           # (exists) Claude client wrapper
│   ├── dashboard/
│   │   ├── app.py                     # (exists) read-only Streamlit entry point
│   │   └── **panels/**                # gauge, histogram, tier_board, paths, change_log, feed_health
│   ├── **mcp/**                       # OPTIONAL read-only MCP server over DuckDB
│   │   └── server.py                  # tools: control odds, state table, conditional scenario, explain last change
│   └── analysis/                      # (exists) ad-hoc notebooks-glue, House roll-ups
└── tests/
    ├── unit/                          # (exists) pure-function tests
    ├── integration/                   # (exists) DuckDB / filesystem
    ├── **replay/**                    # full-night replay + fixtures of archived snapshots
    └── **calibration/**              # reliability / coverage (run nightly, not on every commit)
```

**Note:** move `PROJECT_SPEC.md` into `docs/` for tidiness (optional — it is referenced from
the repo root today).

---

## 4. Required Python packages

Already in the scaffold: `duckdb`, `pandas`, `numpy`, `statsmodels`, `streamlit`,
`anthropic`, `pydantic` + `pydantic-settings`, `python-dotenv`, `PyYAML`, `pytest`
(+ `pytest-cov`, `pytest-mock`, `ruff`, `mypy`).

### 4.1 Add for the core build

| Package | Purpose | Phase |
|---|---|---|
| `scipy` | Student-t & multivariate-normal sampling, linear algebra for the correlation matrix, stats utilities | 1 |
| `APScheduler` | In-process scheduler (event-driven + debounce + 2-min backstop). Replaces Prefect/Dagster per spec | 2 |
| `httpx` | Feed HTTP client with timeouts/retries (preferred over `requests`) | 2 |
| `tenacity` | Declarative retry/backoff for flaky feeds | 2 |
| `pyarrow` | Parquet export (nightly warehouse + read-only reader snapshot) | 2 |
| `slack_sdk` | Slack alert delivery (or a thin webhook via `httpx` if you prefer zero deps) | 3 |
| `plotly` *(or `altair`)* | Dashboard gauge / seat histogram (Streamlit renders either natively) | 3 |

### 4.2 Add for testing & calibration

| Package | Purpose | Phase |
|---|---|---|
| `hypothesis` | Property-based tests (matrix PSD, seat-sum invariants, attribution sums) | 1 |
| `playwright` | Dashboard smoke test (panels render, no console errors) + replay-at-speed verification | 3 |
| `freezegun` | Deterministic time in scheduler/prior-fade tests | 2 |

### 4.3 Optional / stretch

| Package | Purpose | When |
|---|---|---|
| `mcp` | Read-only MCP server for Claude Desktop Q&A | Phase 4, optional |
| `scikit-learn` | Convenience for the swing regression (otherwise use `statsmodels` OLS) | only if it saves time |
| `pandera` | DataFrame schema validation at ingestion boundaries | if time permits |
| `pymc` / `cmdstanpy` | Hierarchical pooling | **out of scope for v1** |

**Principle:** every added dependency is a 1 am failure point. The list above is deliberately
short; prefer NumPy/SciPy over a framework wherever the framework only saves a few lines.

---

## 5. DuckDB schema plan

One file, append-only where it matters, with a `runs` table that makes every output
reproducible. Partition large append-only tables logically by `state`. Full DDL lives in
`data/storage/schema.sql`; the plan:

### 5.1 Reference / canonical entities (mostly static, loaded pre-election)

| Table | Key | Core columns |
|---|---|---|
| `races` | `race_id` | state, office, is_special, seat_class, counting_rule (`plurality`/`runoff`/`rcv`), incumbent_party, recount_band_pts |
| `candidates` | `candidate_id` | race_id, name, party, is_incumbent, caucus_party (nullable, for independents) |
| `reporting_units` | `unit_id` (FIPS; town for ME/NH) | state, name, unit_type, registered_voters, votes_2024_by_method (JSON), demographics (JSON: edu/age/race/density) |
| `senate_holdovers` | `seat_id` | party, up_for_election (bool) — **read seat math from here; never hard-code 30+** |

### 5.2 Append-only input streams (never overwritten)

| Table | Key | Core columns |
|---|---|---|
| `polls` | `poll_id` | race_id, pollster, pollster_grade, field_start, field_end, population (LV/RV), mode, sample_n, margin_d_minus_r, sponsor, house_effect_adj, ingest_ts |
| `fundamentals` | (race_id, as_of) | pres_margin_2024, generic_ballot, approval, incumbency, candidate_quality, midterm_penalty |
| `market_ticks` | (venue, contract, ts) | price, volume, spread |
| `result_snapshots` | `snapshot_id` | unit_id, race_id, source, source_ts, ingest_ts, votes (JSON per candidate), ballots_counted, vote_method, quarantined, quarantine_reason |
| `expected_vote` | (unit_id, source, ts) | expected_total, lo, hi |
| `events` | `event_id` | type (lawsuit/extended-hours/outage/AP-call), state, ts, payload (JSON), source |

### 5.3 Run tracking & outputs (one write set per worker tick)

| Table | Key | Core columns |
|---|---|---|
| `runs` | `run_id` | started_ts, finished_ts, regime (`pre`/`live`), trigger, inputs_hash, seed, n_sims, **code_version (git SHA)**, status |
| `state_forecasts` | (run_id, race_id) | mu_margin, sigma_margin, p_win_d, p_win_r, p_over_50 (GA, nullable), drivers (JSON) |
| `sim_outputs` | `run_id` | p_r_control, p_d_control, mc_stderr, r_seats_median, r_seats_p10, r_seats_p90, seat_histogram (JSON), paths (JSON), conditionals (JSON) |
| `ratings` | (run_id, race_id) | label, p_leader, prev_label, changed |
| `leverage` | (run_id, race_id) | control_leverage, tipping_point_prob, criticality, expected_info_gain |
| `attributions` | (run_id, prev_run_id, target) | target_kind (`state`/`source`), target_id, contribution_pts |
| `narratives` | `run_id` | text, validated, approved, approver, created_ts |
| `alerts` | `alert_id` | run_id, severity, type, state, message, dedup_key, created_ts, sent_channels, acknowledged |
| `feed_health` | source | last_ok_ts, last_lag_s, status, quarantined_count |

### 5.4 Schema invariants (enforced in `repository.py`, tested)

- A `result_snapshot` with totals lower than the prior accepted snapshot for the same unit is
  **rejected** (quarantined) unless it carries a correction flag.
- A county exceeding **110%** of registered turnout is quarantined.
- Two feeds differing beyond tolerance → quarantine + P3 alert; prefer the most recent valid snapshot.
- Every row in an output table references a valid `run_id`; outputs for a run are written in a
  single transaction so readers never see a half-written run.
- `inputs_hash` is computed over the exact input rows consumed; identical hash + seed + code_version ⇒ identical outputs (replay test).

---

## 6. Historical calibration strategy

Calibration is where forecasts are actually validated. Given the timeline, it is **tiered**:
a mandatory floor plus stretch depth.

### 6.1 Mandatory floor (must pass before Nov 2)

1. **Error-structure priors from literature, not fitting.** Set the national-error σ (3–5 pt,
   midterm Senate) and Student-t dof (≈5) from historical knowledge; do **not** burn days
   trying to estimate them from scratch.
2. **One full 2022 live replay.** Drive archived (or best-available reconstructed) county
   snapshots through the live engine end to end. Measure: how early the control call stabilises,
   how many times it flips, and whether intermediate probabilities look sane.
3. **Interval-coverage sanity on the pre-election model** against the **actual 2022 Senate
   outcomes** (state-level margins): the 80% margin interval should contain the realised margin
   ~80% of the time. Accept **75–85%**.
4. **Reproducibility test.** Same inputs + seed + code SHA → byte-identical `sim_outputs`.

### 6.2 Stretch (do only if Phase 1–2 finish early)

- Multi-cycle backtest on **2014 / 2018 / 2022** (and 2024 for live-mode drift), point-in-time
  (only data available at forecast time).
- **Reliability curves per tier**: of races given 70%, ~70% should have been won. Report Brier
  score and log-loss per tier.
- **Leave-one-cycle-out** tuning of the prior-fade exponent `k`, poll half-life `λ`, and blend
  variances — with heavy regularisation, because 3–4 cycles overfit trivially.

### 6.3 Metrics module (`calibration/metrics.py`)

- `brier_score`, `log_loss` (per tier and overall)
- `reliability_curve` (binned predicted vs. realised frequency)
- `interval_coverage` (nominal vs. empirical for the 80% band)
- `sharpness` (interval width — a model can be well-calibrated and useless if intervals are huge)

### 6.4 Acceptance gates (block the "freeze" at Phase 4)

- ☐ 80% interval coverage within **75–85%** on the 2022 check
- ☐ Reliability not catastrophically off in any populated tier
- ☐ Full 2022 night replay completes **with no manual intervention**
- ☐ Reproducibility test green

**Biggest risk restated:** if archived county snapshots cannot be obtained in time, 6.1(2)
degrades to a **state-level** replay (coarser but still informative), and the county live model
is validated with synthetic/injected snapshots instead. Decide this by end of Phase 0.

---

## 7. Forecast-engine design (pre-election, deterministic)

Produces, per race, a **distribution of the two-party margin** `(D − R, in points)` →
`StateForecast(mu_margin, sigma_margin, drivers[])`. Win probability is derived, not primary.

**Pipeline (pure functions, no I/O, no LLM):**

1. **Polling average** (`forecast/polls.py`). Weight each poll
   `w = q_pollster · min(√n, cap) · e^(−λ·age) · ρ_LV`, after subtracting the pollster's
   house effect. Cap any single pollster at ≈25% of a state's weight; half-life 7–10 days this
   late. Output: `(mu_poll, sigma_poll)` per state.
2. **Fundamentals prior** (`forecast/fundamentals.py`). Regression on 2024 presidential lean,
   national environment (generic ballot, approval), incumbency/candidate quality, midterm
   penalty → `(mu_fund, sigma_fund)`.
3. **Bayesian blend** (`forecast/blend.py`). Precision-weighted posterior
   `mu = (mu_poll/σ²_poll + mu_fund/σ²_fund) / (1/σ²_poll + 1/σ²_fund)`. Thin-poll states get
   large `σ_poll`, so fundamentals dominate automatically (and their σ is widened by hand in
   lieu of hierarchical pooling).
4. **Pooling** (`forecast/pooling.py`). **v1 = stub** (identity). Documented as the first
   stretch upgrade.
5. **Market/ratings check** (consumed in `ratings/` + `alerts/`). Never averaged in; a
   model-vs-market gap > ≈15 pts in a Tier-1 state raises a P2 flag.
6. **Special cases** (`forecast/specials.py`):
   - **RCV (ME, AK):** model first-round shares + a sampled transfer matrix with its own uncertainty.
   - **GA:** output `P(any candidate > 50%)` alongside `P(win)`; a runoff ⇒ "unresolved, Dec runoff".
   - **Independents (e.g. NE):** separate candidate + a caucus-alignment probability for chamber counting.

**Output contract:** every `StateForecast` carries a `drivers` list (named factor,
contribution in points) so attribution and narrative can consume it without re-deriving anything.

---

## 8. Simulation-engine design (shared Monte Carlo)

The single most important module. **Pure, vectorised, seeded, regime-agnostic.**

**Signature (conceptual):** `simulate(state_forecasts, correlation_config, seed, n_sims) → SimResult`

**Error structure** (`simulate/correlation.py`), per spec:
`M_s = μ_s + ε_nat + βₛ·η + ε_s`
- `ε_nat` — one draw per simulation, **Student-t (dof ≈ 5)** for fat tails (a wave must not be
  "impossible"). σ from backtests/literature (3–5 pt).
- `βₛ·η` — a few demographic factors (e.g. non-college-white, Hispanic-voter); each state's
  loading `βₛ` from its demographic mix. **Loadings fixed in v1** (the pooling substitute).
- `ε_s` — state-specific noise, larger for thin-poll states.

**Per-simulation steps** (`simulate/engine.py` → `outcomes.py`):
1. Draw national, factor, and state errors (vectorised: shape `[n_sims, n_states]`).
2. Compute margins; apply sampled RCV transfer for ME/AK; apply GA 50% rule.
3. Assign winners; **add holdover seats read from `senate_holdovers`** (never hard-coded).
4. Apply caucus-alignment draws for independents.
5. Control: **R ≥ 50 ⇒ R control (VP tiebreak); D ≥ 51 ⇒ D control**; record "undetermined
   pending runoff" where a GA runoff could decide it.

**Scale & guarantees:** 50k–100k sims per run, well under a second vectorised. **Seed = run_id**
⇒ exact replay. Report MC standard error (target < 0.3 pt at 100k).

**Outputs** (`sim_outputs` + `paths.py`, `conditionals.py`): `P(control)` per party + MC
stderr; seat histogram + median + 80% interval; top seat-combination paths grouped by Tier-1
winners; full conditional table `P(control | party wins s)` for every Tier-1 state.

**Live mode:** same engine, inputs swapped to the live posterior; called states **pinned**;
correlation still applied to outstanding-vote error across similar (e.g. mail-heavy) counties.

---

## 9. Election-night architecture (live regime)

**One worker, five steps per tick, event-driven with a backstop.**

```
         accepted snapshot (Tier-1)            every 2 min (backstop)
                  │                                     │
                  └──────────► scheduler (debounce 30s) ◄┘
                                     │
   ┌─────────────────────────────────┼─────────────────────────────────┐
   │ 1 FETCH        2 PROJECT         3 SIMULATE      4 COMPARE   5 ALERT │
   │ adapters   →   live engine   →   shared MC   →   attribution → rules │
   │ + reconcile    (county proj,     (pinned calls)  vs prev run  + Slack│
   │ + quarantine   swing, fade)                      + ratings          │
   └──────────────────────────────── writes one `runs` row ─────────────┘
                                     │
              readers (read-only): Streamlit dashboard · optional MCP server
```

**Live engine** (`live/`):
- **County projection** (`county_projection.py`): for each unit estimate expected total `E_c`
  and counted share `r_c`; observe counted margin; **predict the margin of what's *left*** from
  the outstanding vote method (mail vs. Election Day) × that county's 2024 method split, shifted
  by observed swing; blend counted + predicted-outstanding; sum to state.
- **Swing learning** (`swing.py`): regress swing-vs-2024 on demographics as counties finish;
  apply fitted swing to not-yet-reporting counties ("the needle"). Fit national + per-state,
  partially pooled.
- **Cross-state** (`cross_state.py`): early-closing states (GA, NH) feed the national swing
  estimate into late states' priors **before they report**.
- **Prior fade** (`prior_fade.py`): `α = (1 − pct_expected_in)^k`, `k ≈ 2`; prior still matters
  at 30% in, nearly gone by 80%. **Uncertainty scales with outstanding vote, not with the lead.**
- **Guardrails** (`guardrails.py`): no single snapshot moves a state > ~15 pts of probability
  without a second confirming snapshot; AP/DDHQ calls → `P = 0.995` (retractable); stale feed
  > 10 min during counting → **widen** the interval, don't hold; projected margin inside the
  recount band → emit "likely recount".

**Ingestion & resilience** (`data/ingestion/`): one idempotent adapter per source writing to
append-only `result_snapshots`; dual feeds + reconciliation/quarantine; recorded source lag;
a **kill switch** to pin any source to "ignored" without a deploy; a manual-entry path.

**Operational substrate:** worker in `tmux` on a 1 vCPU / 2 GB VM under `systemd` restart;
dashboard on the same box; **DuckDB backup every 15 min** to object storage; laptop cold
standby with code + DB copy. **Stale-worker alarm** (P1 if last successful run age exceeds
threshold during counting).

**Human-in-the-loop:** projections enter a "pending" state until approved in the dashboard;
every override (pin/hold/approve) is logged with a reason.

---

## 10. Testing strategy

Pyramid, with replay and calibration as a separate (slower) tier run off the commit path.

| Layer | What | Tools / markers |
|---|---|---|
| **Unit** (`-m unit`) | Pure functions: poll weighting, house-effect removal, Bayesian blend, swing regression, prior fade, seat counting, control rule, RCV transfer, GA 50% rule, hysteresis bands | `pytest`, `freezegun` |
| **Property** (within unit) | Correlation matrix is PSD; `P(control) ∈ [0,1]`; R_seats within valid range; **attribution contributions sum to the total move** (±tol); monotonicity: more R margin ⇒ `P(R control)` non-decreasing | `hypothesis` |
| **Integration** (`-m integration`) | DuckDB round-trips, repository invariants (totals-decrease rejection, 110% turnout quarantine, atomic run write), read-only reader connections | `pytest`, DuckDB |
| **Determinism / golden-master** | Same inputs + seed + SHA ⇒ identical `sim_outputs`; golden fixture for a known input set | `pytest` |
| **Feed robustness** | Garbage snapshot quarantined + alerted; decreasing totals rejected; stale feed widens interval; dual-feed disagreement handled | `pytest` with recorded fixtures |
| **Replay** (`-m replay`) | Full 2022 night end-to-end; kill worker mid-replay and confirm clean resume from DuckDB; run at 1× and 5× | `scripts/replay_night.py` |
| **Calibration** (`-m calibration`, nightly) | Reliability, interval coverage, Brier/log-loss against the acceptance gates (Section 6.4) | `calibration/` |
| **Narrative** | Planted wrong number is rejected; certainty-word filter trips on "will win"; every numeric token traces to the record | `pytest` |
| **Dashboard smoke** | Panels render, no console errors, updates on new run | `playwright` |

**CI (fast):** `unit` + `integration` + determinism on every commit. **Nightly / manual:**
`replay` + `calibration`. The replay test is the spec's headline non-negotiable — treat a red
replay as a release blocker.

---

## 11. Implementation phases

Effort is given in **ideal focused dev-days** (one developer, uninterrupted) with a **risk**
flag. The solo plan compresses these into Oct 29 – Nov 1; where ideal effort exceeds the
calendar, the **scope cut** column says what gives.

> Legend — Risk: 🟢 low · 🟡 medium · 🔴 high (schedule or external dependency)

### Phase 0 — Foundation & data contracts
*(Scaffold already done; this is the data spine.)*
- **Objectives:** lock the schema, the run/reproducibility model, the feed interface, and the
  replay harness skeleton before any modelling.
- **Deliverables:** `schema.sql` + `init_db.py`; `repository.py` with invariants; `runs` table
  with `inputs_hash`/`seed`/`code_version`; `DataSource` adapter contract finalised;
  `replay_night.py` skeleton; **decision recorded** on archived-snapshot availability (Section 6.1/6.4).
- **Dependencies:** none (builds on scaffold).
- **Validation:** DB creates cleanly; repository invariant tests green; a dummy run writes
  atomically and reproduces from `(inputs_hash, seed)`.
- **Effort:** ~1.0 day · Risk: 🟡 (hinges on the snapshot-availability decision).
- **Scope cut if behind:** defer Parquet reader-snapshot; readers open the live file read-only.

### Phase 1 — Pre-election forecast + Monte Carlo core *(spec: Oct 29)*
- **Objectives:** from loaded polls + fundamentals, produce per-state margin distributions and,
  through the correlated simulator, **a control probability that prints**.
- **Deliverables:** `forecast/polls|fundamentals|blend|specials`; `simulate/correlation|engine|
  outcomes|paths|conditionals`; `models/` estimator base reused; literature-prior error
  structure; `cli` command to run one pre-election tick.
- **Dependencies:** Phase 0 (schema, reference data loaded).
- **Validation:** control probability prints end to end; property tests (PSD, seat sums,
  `P∈[0,1]`); reproducibility test green; MC stderr < 0.3 pt at 100k.
- **Effort:** ~1.5 days · Risk: 🟡.
- **Scope cut if behind:** pooling stays a stub (planned); demographic factors reduced to one
  national factor if loadings aren't ready.

### Phase 2 — Live engine + results adapter + replay *(spec: Oct 30)*
- **Objectives:** ingest one result feed, project county→state live, fade the prior by vote
  completeness, and **replay a 2022 night end to end**.
- **Deliverables:** `data/ingestion/adapters/` (one feed) + `reconciliation.py`; `live/
  county_projection|swing|cross_state|prior_fade|guardrails`; `scripts/replay_night.py` working.
- **Dependencies:** Phase 1 (shared simulator), **feed access confirmed** (external).
- **Validation:** 2022 replay completes with no manual intervention; kill-and-resume test green;
  garbage-feed quarantine + stale-feed widening verified.
- **Effort:** ~2.0 days · Risk: 🔴 (feed access + archived snapshot data are the two biggest external risks).
- **Scope cut if behind:** county model for **Tier-1 states only**, state-level elsewhere
  (already the spec's cut); single feed + manual SoS spot-checks.

### Phase 3 — Dashboard + alerts + attribution *(spec: Oct 31)*
- **Objectives:** make the system observable and explainable; ship the read-only dashboard,
  Slack alerts, and swap-based attribution.
- **Deliverables:** `dashboard/panels/` (gauge, seat histogram, Tier-1 board, path tracker,
  change log, feed health); `attribution/shapley.py`; `alerts/rules|dedup|slack.py`;
  `ratings/labels|hysteresis|leverage.py`.
- **Dependencies:** Phases 1–2 (runs + outputs to display; attribution needs consecutive runs).
- **Validation:** attribution contributions sum to the total move (property test); alert volume
  in replay under the agreed per-hour cap; dashboard smoke test green; label changes logged with drivers.
- **Effort:** ~1.5 days · Risk: 🟡.
- **Scope cut if behind:** attribution by **state only** (defer per-source within-state);
  alerts to Slack only (phone push later).

### Phase 4 — Narrative + House + MCP + freeze *(spec: Nov 1)*
- **Objectives:** add constrained prose, the lightweight House module, optionally the MCP
  server; run a full replay at 5×; **freeze at midnight**.
- **Deliverables:** `narrative/templates|generate|validator` (validator is a hard gate);
  `analysis/` House rating-based simulation (2026 district lines) with a joint "R Senate + D
  House" probability; **optional** `mcp/server.py`; full 5× replay.
- **Dependencies:** Phase 3 (narrative needs attribution). House and MCP are independent and may slip.
- **Validation:** validator rejects a planted wrong number and the certainty-word filter; House
  joint probability sane; calibration **acceptance gates** (Section 6.4) pass; 5× replay clean.
- **Effort:** ~1.5 days (House ~0.5, narrative ~0.5, MCP ~0.5) · Risk: 🟡.
- **Scope cut if behind:** **MCP dropped** (optional sixth part); House dropped to Senate-only;
  narrative limited to Tier-1 moves of 3+ points.

### Phase 5 — Operate (Nov 2–8)
- **Objectives:** run reliably, monitor, back up, recover.
- **Deliverables:** VM + `systemd` + `tmux` live; 15-min DuckDB backups; `docs/runbook.md` and
  `docs/break_glass.md`; laptop standby validated.
- **Dependencies:** a green Phase-4 freeze.
- **Validation (pre-flight, from spec):** replay a 2022 night unaided; kill worker mid-replay →
  clean resume; feed returns garbage → quarantine + alert; validator rejects a planted number;
  **results-feed license confirmed**.
- **Effort:** ~0.5 day setup + continuous operation · Risk: 🟡 (operational, not build).
- **Scope cut if behind:** none — this phase *is* the product; earlier scope is cut to protect it.

### 11.1 Effort summary

| Phase | Ideal days | Calendar (solo) | Dominant risk |
|---|---|---|---|
| 0 Foundation | 1.0 | Oct 28–29 | Snapshot-data decision |
| 1 Forecast + MC | 1.5 | Oct 29 | Modelling correctness |
| 2 Live + replay | 2.0 | Oct 30 | 🔴 Feed access + archived data |
| 3 Dashboard + alerts | 1.5 | Oct 31 | UI/alert time sink |
| 4 Narrative + House + MCP | 1.5 | Nov 1 | Scope creep |
| **Core total** | **~7.5 ideal days** | **4 calendar days** | — |

**The honest gap:** ~7.5 ideal dev-days are being compressed into 4 calendar days. That is only
survivable because of the scope cuts already in the spec's "solo replacement" column and the
per-phase cuts above. **Protect the non-negotiables** (correlated MC, outstanding-ballot vote-method
model, stale-feed widening, replay test); let House, MCP, per-source attribution, multi-cycle
calibration, and hierarchical pooling fall away first under schedule pressure.

---

## 12. Immediate next actions (not implementation)

1. **Confirm the results-feed license/access today.** It gates Phase 2 and the whole live product.
2. **Decide archived-snapshot availability** (real 2022 county snapshots vs. state-level vs.
   synthetic). This sets the calibration floor and must be settled by end of Phase 0.
3. **Approve this phase order and the scope-cut priority** so that, under pressure, cuts are
   pre-decided rather than improvised at 1 am.
4. Then, and only then, begin Phase 0 (schema + run model + replay skeleton).

*No code is written until items 1–3 are resolved.*
```
