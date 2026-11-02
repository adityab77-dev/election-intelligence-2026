# Model Validation Report — 2026 Senate Control
Generated from the current pipeline · forecast date 2026-11-01 · 50,000 simulations · seed 2026

> **⚠️ Synthetic data.** These figures come from the **fabricated** `sample_polls.json`
> development dataset (see `src/election_intelligence/data/ingestion/README.md`), **not real
> polls**. This report validates that the *model behaves correctly*, not that these are real
> forecasts. The numbers will change entirely with real polling data.

The figures below were produced by replicating the committed aggregation (Phase 4),
forecast (Phase 5), and Monte Carlo (Phase 6) math on the sample polls.

---

## 1. Per-state forecast distributions

Margin is **D − R** (positive = Democrat ahead). Win probability is implied by the forecast
distribution `Normal(mean, sigma)`: `P(D win) = Φ(mean / sigma)`.

| State | Race | Mean margin | σ | P(D win) | P(R win) | Favored |
|-------|------|------------:|-----:|--------:|--------:|---------|
| NH | NH-2026 | **D +5.8** | 3.98 | 92.7% | 7.3% | D (Likely) |
| MI | MI-2026 | **D +3.7** | 3.98 | 82.3% | 17.7% | D (Likely) |
| NC | NC-2026 | **D +2.8** | 3.98 | 75.7% | 24.3% | D (Lean) |
| GA | GA-2026 | **D +1.8** | 3.97 | 67.8% | 32.2% | D (Lean) |
| ME | ME-2026 | **D +0.2** | 3.97 | 52.2% | 47.8% | **Toss-up** |
| OH | OH-2026-S | **R +1.3** | 4.01 | 37.8% | 62.2% | R (Lean) |
| TX | TX-2026 | **R +2.4** | 3.99 | 27.1% | 72.9% | R (Lean) |
| IA | IA-2026 | **R +2.9** | 3.97 | 23.6% | 76.4% | R (Lean) |

**Validation observation:** every σ is ≈ 4.0, almost flat across states. This is expected and
correct — σ is dominated by the **3.5-point systematic polling-miss floor**, with the
poll-sampling/dispersion term adding only ~0.5–1.0 on top (the synthetic polls are tightly
clustered, with 5 polls per race). All eight therefore land at **Medium** confidence. With
real, more dispersed polling, the per-state variance term would separate these more.

---

## 2. How the Republican Senate probability is calculated

It is **not** a formula applied to the eight numbers above — it is the fraction of 50,000
simulated elections in which Republicans hold the chamber:

1. **Per-state distribution** — each race becomes `Normal(mean_margin, σ)` from §1.
2. **Correlated draws** — in each of the 50,000 simulations, one **shared national error**
   (σ = 3.0, identical for all states) is drawn, plus an **independent state error** per race.
   Each state's total σ is split so the shared 3.0 is carved out of it:
   `state_margin = mean + national_error + state_error`. This makes the eight races move
   *together*.
3. **Seat counting** — a state goes R if its drawn margin < 0.
   `R total = 48 (baseline non-battleground seats) + R battleground wins`.
4. **Control rule** — Republicans control at **≥ 50** seats (the VP breaks ties); Democrats
   need **≥ 51**.
5. **Probability** — the share of the 50,000 simulations with R ≥ 50.

**Result: Republican Senate 78% / Democratic 22%, expected seats R 51.4 / D 48.6**
(Monte Carlo standard error **0.18 pp** — well inside the 0.3 pp target; ~0.13 pp at 100k).

**The most important validation point:** if the eight races were treated as *independent*,
R control would come out at **~98%** (R is favored in TX/OH/IA and only needs 2 of 8). The
correlated national error pulls it down to **78%** — because a single bad-polling-miss draw can
sink TX, OH *and* IA at once. This is exactly the behaviour the specification demands
("correlation is the model"); treating seats as independent would badly overstate the favorite.

---

## 3. Which states contribute most to uncertainty

Two distinct notions, worth separating:

**Most uncertain as individual races** (closest to a coin flip): **ME (47.8% R)** is the single
most uncertain race, followed by **OH (62.2% R)** and **GA (67.8% D)**. NH (92.7% D) and
MI (82.3% D) are nearly settled and contribute little.

**Most contribution to control-probability uncertainty** — race uncertainty **weighted by how
much the race swings control** (criticality = leverage × race-uncertainty):

| Rank | State | Criticality | Why |
|------|-------|------------:|-----|
| 1 | **TX** | 0.235 | Lean-R but live, and highly pivotal |
| 2 | **OH** | 0.232 | Nearest-to-tossup of the R seats |
| 3 | **IA** | 0.223 | Highest leverage, modest residual doubt |
| 4 | **ME** | 0.194 | A true toss-up, but lower leverage |
| 5 | GA | 0.137 | Uncertain but rarely decisive |

The chamber's uncertainty is concentrated in the **three lean-R seats (TX, OH, IA) plus Maine**
— not in the safe-D states, and not purely in the closest race (ME). Resolving TX/OH/IA would
collapse most of the control-probability variance.

---

## 4. Which states drive the outcome

Measured by **control leverage** = `P(R control | R wins state) − P(R control | D wins state)`
— how much the chamber hinges on each state:

| State | Leverage | Role |
|-------|---------:|------|
| **IA** | +0.618 | **Tipping-point** — the pivotal seat |
| **TX** | +0.595 | Co-pivotal; large electoral weight |
| **OH** | +0.494 | The swing that most often decides control |
| ME | +0.389 | Matters in the closest scenarios |
| GA | +0.313 | Secondary |
| NC | +0.283 | Secondary |
| MI | +0.263 | Low — nearly always D |
| NH | +0.233 | Lowest — effectively settled |

**The outcome is driven by the three lean-Republican seats — Iowa, Texas, Ohio.** Because
Republicans start from a 48-seat baseline and need just 2 of the 8 battlegrounds, these are the
seats that most often land *on* the 50-seat line across simulations. The safe-D states (NH, MI)
have low leverage: they rarely change who controls the chamber. **Maine**, despite being the
closest race, has *lower* leverage than the lean-R trio — a close race is not the same as a
decisive one, exactly the distinction the specification draws.

---

## Net validation verdict

The model behaves as designed:

- correlation materially lowers the favorite's odds (98% independent → 78% correlated);
- leverage correctly separates "close" (ME) from "decisive" (IA/TX/OH);
- Monte Carlo standard error is within target (0.18 pp at 50k);
- σ is sensibly floor-dominated given the tightly-clustered synthetic inputs.

The headline numbers are only as real as the data, which is currently **synthetic**. Replace
`sample_polls.json` with real polling (per `REFERENCE_DATA_CHECKLIST.md`) before treating any of
these figures as an actual forecast.
