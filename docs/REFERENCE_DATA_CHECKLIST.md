# Reference Data Checklist & Inventory
**2026 Senate Control Intelligence System**
Prepared: 2026-10-29 · Clears the Phase 2 gate in [`BUILD_PLAN.md`](BUILD_PLAN.md) §C.4

> Complete inventory of every dataset the project consumes. For each: purpose, source,
> availability, cost, licensing, a backup source, and V1-vs-optional status. Ranked by
> implementation priority at the end (Section Z).
>
> **Caveats:** all costs are **approximate — verify at point of purchase**. Licensing terms
> change; confirm before any redistribution. Dollar amounts are directional, not quotes.
> **FiveThirtyEight note:** after ABC's 2025 restructuring, 538's *live* 2026 updates are
> uncertain; its *historical* CSVs remain on GitHub. Current-cycle primaries below are chosen
> accordingly.

---

## Legend
- **Availability:** 🟢 easy (download/API now) · 🟡 obtainable with effort (scrape/clean/request) · 🔴 hard/gated (paid contract, access approval, or may not exist in usable form)
- **V1 status:** **Required** (blocks a working forecast) · **Degradable** (required but has a lesser fallback) · **Optional** (stretch / post-v1)

---

## A. Polling & pollster quality

### A.1 Historical polling (past cycles)
| Field | Detail |
|---|---|
| **Purpose** | Estimate pollster accuracy & house effects; calibrate poll-decay and blend variances |
| **Source** | FiveThirtyEight historical polls CSVs (GitHub `fivethirtyeight/data`); Roper Center iPoll (academic) |
| **Availability** | 🟢 (538 CSVs) / 🟡 (Roper, institutional login) |
| **Cost** | Free (538); Roper free with academic affiliation |
| **Licensing** | 538 data CC-BY-4.0 (attribute); Roper academic-use terms |
| **Backup source** | 270toWin historical poll pages; Wikipedia cycle poll tables (CC-BY-SA) |
| **V1 status** | **Degradable** — needed only to *derive* grades (A.3); skip if using published grades |

### A.2 Current polling (2026 cycle)
| Field | Detail |
|---|---|
| **Purpose** | The primary pre-election signal per state (Phase 4 aggregation) |
| **Source** | RealClearPolling (RCP) Senate pages; Silver Bulletin; Wikipedia "2026 United States Senate elections" (sourced tables); pollster press releases |
| **Availability** | 🟡 — RCP/Wikipedia are HTML (scrape + parse); no clean free bulk API |
| **Cost** | Free (scrape); Silver Bulletin data behind paid substack |
| **Licensing** | RCP terms restrict scraping/redistribution — **personal/internal use only**, verify; Wikipedia CC-BY-SA |
| **Backup source** | 538 (if live in 2026), Decision Desk HQ/The Hill polling page, VoteHub, individual pollster sites |
| **V1 status** | **Required** |

### A.3 Pollster grades & house effects
| Field | Detail |
|---|---|
| **Purpose** | The `q_pollster` weight and the house-effect subtraction in Phase 4 |
| **Source** | FiveThirtyEight Pollster Ratings (grades + bias, published CSV + methodology); Silver Bulletin pollster ratings |
| **Availability** | 🟢 (historical 538 CSV) / 🟡 (latest ratings) |
| **Cost** | Free |
| **Licensing** | 538 CC-BY-4.0; Silver Bulletin terms vary |
| **Backup source** | AAPOR Transparency Initiative membership list (as a crude quality proxy); derive your own from A.1 |
| **V1 status** | **Degradable** — fallback: uniform weights + capped single-pollster influence if grades unavailable |

---

## B. Historical election results (calibration & baselines)

### B.1 Historical Senate results (1976–2024)
| Field | Detail |
|---|---|
| **Purpose** | Backtest/calibration (Phase 8); partisan-lean baselines |
| **Source** | MIT Election Data & Science Lab (MEDSL) "U.S. Senate 1976–2020" on Harvard Dataverse (+ newer releases) |
| **Availability** | 🟢 |
| **Cost** | Free |
| **Licensing** | CC-BY (attribute MEDSL) |
| **Backup source** | Official: U.S. Senate.gov historical election results; Wikipedia |
| **V1 status** | **Required** (for calibration) |

### B.2 Historical House results (1976–2024)
| Field | Detail |
|---|---|
| **Purpose** | House module calibration & national-swing baselines |
| **Source** | MEDSL "U.S. House 1976–2022"; Clerk of the U.S. House official results (`clerk.house.gov`) |
| **Availability** | 🟢 |
| **Cost** | Free |
| **Licensing** | CC-BY (MEDSL); official results public domain |
| **Backup source** | Wikipedia; Daily Kos Elections data sheets |
| **V1 status** | **Optional** (House module is optional) |

### B.3 County-level results (2016–2024, incl. 2024 by seat)
| Field | Detail |
|---|---|
| **Purpose** | County baselines for the live "needle" swing model (Phase 9); correlation structure |
| **Source** | MEDSL county presidential 2000–2020; Dave Leip's Atlas (comprehensive county, incl. Senate); OpenElections |
| **Availability** | 🟡 — presidential county 🟢; **county-level Senate is spotty** (Leip best, paid; OpenElections incomplete) |
| **Cost** | Free (MEDSL/OpenElections); Leip ~$35–250 one-time (verify tier) |
| **Licensing** | MEDSL CC-BY; OpenElections public-domain/CC0-style; **Leip = personal use, no redistribution** |
| **Backup source** | State SoS historical result archives (scrape) |
| **V1 status** | **Degradable** — Tier-1 states only; state-level elsewhere |

---

## C. Vote method, demographics, geography

### C.1 Vote-method data (early/mail/Election-Day shares)
| Field | Detail |
|---|---|
| **Purpose** | Model the margin of *outstanding* ballots — the non-negotiable late-count-drift model (Phase 9) |
| **Source** | U.S. Elections Project (`electproject.org`, McDonald) early/mail stats; Census CPS Voting Supplement; state SoS method splits |
| **Availability** | 🟡 historical shares / 🔴 **live method-mix during counting** (many states don't report method live) |
| **Cost** | Free |
| **Licensing** | USEP academic/open; Census public domain |
| **Backup source** | AP/DDHQ live method tags where provided; state absentee files; party-registration splits |
| **V1 status** | **Degradable** — historical 2024 method shares **Required** for the model; live method is **best-effort** per state (validate availability — pre-coding gate A.4-3) |

### C.2 Demographics (county-level)
| Field | Detail |
|---|---|
| **Purpose** | Demographic error-factor loadings (β) for correlation (Phase 6); swing regressors (Phase 9) |
| **Source** | U.S. Census ACS 5-year, county-level (Census API / `data.census.gov`): education, age, race, density |
| **Availability** | 🟢 |
| **Cost** | Free |
| **Licensing** | Public domain (U.S. Government work) |
| **Backup source** | IPUMS NHGIS (harmonized Census); pre-packaged MEDSL demographic joins |
| **V1 status** | **Required** (even reduced to one demographic axis) |

### C.3 House district boundaries (2026 enacted lines)
| Field | Detail |
|---|---|
| **Purpose** | Map House races to 2026 districts (post mid-decade redistricting) — House module |
| **Source** | Redistricting Data Hub (`redistrictingdatahub.org`); Dave's Redistricting App; Census TIGER/Line CD shapefiles |
| **Availability** | 🟡 — **TIGER may lag mid-decade changes (e.g. TX 2025)**; RDH/DRA carry enacted maps |
| **Cost** | Free (registration for RDH) |
| **Licensing** | RDH/DRA open for non-commercial; Census public domain |
| **Backup source** | State legislature / redistricting-commission enacted map files |
| **V1 status** | **Optional** (House module optional) |

---

## D. Election-night live feeds

### D.1 Official results feed (live counts)
| Field | Detail |
|---|---|
| **Purpose** | The live product's core input (Phase 9) — counted votes, ballots counted, calls, sometimes method |
| **Source** | **AP Elections API** (gold standard); **Decision Desk HQ API** |
| **Availability** | 🔴 — **paid, licensed, contracted** |
| **Cost** | Commercial/negotiated — typically **$$$–$$$$ (thousands+)**, often prohibitive for a solo dev (**verify / request quote**) |
| **Licensing** | **Restrictive**: redistribution and display limits; confirm terms cover your intended use (pre-coding gate A.4-1) |
| **Backup source** | **State SoS / county result pages** (free, scrape, heterogeneous) + **manual-entry path** for Tier-1 counties |
| **V1 status** | **Required** — but the realistic solo path is **SoS scrape + manual entry** for Tier-1, not a paid API |

### D.2 Expected-vote / turnout model feed
| Field | Detail |
|---|---|
| **Purpose** | Estimate total expected ballots & % counted — drives live uncertainty (Phase 9) |
| **Source** | AP/DDHQ expected-vote (bundled with D.1); **own county turnout model** from 2024 turnout + registration |
| **Availability** | 🔴 (vendor) / 🟡 (build your own) |
| **Cost** | Bundled with D.1, or free if self-built |
| **Licensing** | Vendor terms, or none if self-built |
| **Backup source** | Self-built turnout model from Census/SoS registration + 2024 turnout |
| **V1 status** | **Required** — **build your own** if no vendor feed (the spec assumes a self-model anyway) |

### D.3 Archived election-night snapshots (2022, point-in-time)
| Field | Detail |
|---|---|
| **Purpose** | Replay framework & live-engine calibration (Phase 7) |
| **Source** | Your own recorded AP/DDHQ stream (if licensed historically); academic archives; OpenElections timestamped captures |
| **Availability** | 🔴 — **point-in-time county snapshots are hard to obtain cleanly** |
| **Cost** | Free–vendor, depends on source |
| **Licensing** | As per originating feed |
| **Backup source** | **State-level** replay from final results; **synthetic** snapshot generator that interpolates final→partial |
| **V1 status** | **Degradable** — county snapshots ideal; state-level or synthetic fallback (pre-coding gate A.4-2) |

---

## E. Structural reference (calendars, rules, roster)

### E.1 State election calendars & counting rules
| Field | Detail |
|---|---|
| **Purpose** | RCV (ME/AK), runoff (GA 50%+1), recount bands, mail-ballot deadlines, regime-switch logic (Phase 3/9) |
| **Source** | NCSL (`ncsl.org`) election rules; Ballotpedia; state SoS; NASS |
| **Availability** | 🟢 (NCSL/Ballotpedia) |
| **Cost** | Free |
| **Licensing** | NCSL/Ballotpedia terms (attribute; verify reuse); SoS public records |
| **Backup source** | State statutes directly; FVAP deadlines |
| **V1 status** | **Required** |

### E.2 Poll closing times (per state, time-zone aware)
| Field | Detail |
|---|---|
| **Purpose** | Freeze pre-election inputs at each state's close; order live-regime switches (Phase 3/9) |
| **Source** | AP / 270toWin poll-close tables; Ballotpedia; state SoS |
| **Availability** | 🟢 |
| **Cost** | Free |
| **Licensing** | Public reference; attribute aggregators |
| **Backup source** | Wikipedia; direct SoS |
| **V1 status** | **Required** (watch states spanning two time zones) |

### E.3 Senate holdover roster & 2026 race set
| Field | Detail |
|---|---|
| **Purpose** | Seats *not* up (held-over) added in the simulator; current 53–47 composition; specials (FL, OH) (Phase 3/6) |
| **Source** | U.S. Senate.gov; Wikipedia "2026 United States Senate elections"; 270toWin |
| **Availability** | 🟢 |
| **Cost** | Free |
| **Licensing** | Official public domain; Wikipedia CC-BY-SA |
| **Backup source** | Clerk/Congress.gov member rosters |
| **V1 status** | **Required** — **read holdover count from this table; never hard-code** |

### E.4 Candidate list, incumbency & counting flags (2026)
| Field | Detail |
|---|---|
| **Purpose** | Per-race candidates, party, incumbency, independent/caucus flags (Phase 3/5) |
| **Source** | Ballotpedia race pages; state SoS candidate filings |
| **Availability** | 🟢 |
| **Cost** | Free |
| **Licensing** | Ballotpedia terms; SoS public |
| **Backup source** | Wikipedia race pages; FEC candidate registrations |
| **V1 status** | **Required** |

---

## F. Fundamentals & supplementary inputs

### F.1 Fundamentals regressors (lean, environment)
| Field | Detail |
|---|---|
| **Purpose** | Prior in the Bayesian blend (Phase 5): 2024 pres margin by state, generic ballot, presidential approval, midterm penalty |
| **Source** | 2024 pres results — MEDSL/official; generic ballot & approval — RCP/538 averages |
| **Availability** | 🟢 (2024 results) / 🟡 (scrape averages) |
| **Cost** | Free |
| **Licensing** | MEDSL CC-BY; aggregator terms for averages |
| **Backup source** | Gallup approval; Wikipedia generic-ballot tables |
| **V1 status** | **Required** |

### F.2 Candidate quality / fundraising
| Field | Detail |
|---|---|
| **Purpose** | Candidate-quality proxy in fundamentals (Phase 5) |
| **Source** | FEC API (`fec.gov`, free); Ballotpedia for prior office/scandal flags |
| **Availability** | 🟢 |
| **Cost** | Free |
| **Licensing** | FEC public domain |
| **Backup source** | OpenSecrets (ad/spending); manual scandal flags |
| **V1 status** | **Optional** (minor weight; folds into candidate quality) |

### F.3 Expert ratings
| Field | Detail |
|---|---|
| **Purpose** | Prior anchor / sanity check (Phase 5), rating cross-reference |
| **Source** | Sabato's Crystal Ball (free); Cook Political Report (partial free/paid); Inside Elections (paid) |
| **Availability** | 🟢 Sabato / 🟡 Cook / 🔴 Inside Elections |
| **Cost** | Free (Sabato) / subscription (Cook, Inside) |
| **Licensing** | Reuse restricted — **cite, don't redistribute**; verify |
| **Backup source** | Sabato alone suffices as anchor |
| **V1 status** | **Optional** (~0.05 weight) |

### F.4 Prediction markets
| Field | Detail |
|---|---|
| **Purpose** | **Calibration check only — never an input** (Phase 5/alerts) |
| **Source** | Kalshi API; Polymarket API; PredictIt API |
| **Availability** | 🟢 |
| **Cost** | Free (public endpoints; verify rate limits/terms) |
| **Licensing** | API terms of service; non-commercial use likely fine |
| **Backup source** | Any one of the three suffices |
| **V1 status** | **Optional** (divergence alert, not a signal) |

### F.5 News / event flags
| Field | Detail |
|---|---|
| **Purpose** | Lawsuits, extended hours, tabulator outages → event flags (Phase 9) |
| **Source** | AP/Reuters wires; SoS press; manual entry |
| **Availability** | 🟡 |
| **Cost** | Free (manual) |
| **Licensing** | Headlines not redistributable; store flags, not text |
| **Backup source** | Manual analyst entry |
| **V1 status** | **Optional** — **manual entry for v1** (LLM triage dropped per build plan) |

---

## Z. Priority ranking (implementation order)

Ranked by *when the build needs it* and *whether it blocks a working forecast*. **P0** items gate
the first printed probability; **P3** items are stretch.

### P0 — Blocks the first forecast (get these first; most are free & easy)
| # | Dataset | Why now | Phase | Avail |
|---|---|---|---|---|
| 1 | **Senate holdover roster & 2026 race set** (E.3) | Seat math; simulator can't run without it | 3,6 | 🟢 |
| 2 | **Candidate list & counting flags** (E.4) | Defines races, RCV/runoff/independent handling | 3,5 | 🟢 |
| 3 | **State calendars & counting rules** (E.1) | RCV/runoff/recount/regime logic | 3,9 | 🟢 |
| 4 | **Poll closing times** (E.2) | Input-freeze & regime switch | 3,9 | 🟢 |
| 5 | **Current 2026 polling** (A.2) | Primary pre-election signal | 3,4 | 🟡 |
| 6 | **Fundamentals regressors** (F.1) | Prior in the blend | 5 | 🟢/🟡 |
| 7 | **County demographics (ACS)** (C.2) | Correlation loadings | 6,9 | 🟢 |

### P1 — Required for calibration & a credible model (close behind P0)
| # | Dataset | Why | Phase | Avail |
|---|---|---|---|---|
| 8 | **Pollster grades & house effects** (A.3) | Poll weighting quality (fallback: uniform) | 4 | 🟢/🟡 |
| 9 | **Historical Senate results** (B.1) | Backtest / coverage check | 8 | 🟢 |
| 10 | **2024 county results by vote method** (B.3 + C.1) | Live outstanding-ballot model baselines | 9 | 🟡 |

### P2 — Live-night essentials (the hard, gated items — resolve early even though used late)
| # | Dataset | Why | Phase | Avail |
|---|---|---|---|---|
| 11 | **Official live results feed** (D.1) | The live product — **but solo path = SoS scrape + manual** | 9 | 🔴 |
| 12 | **Expected-vote model** (D.2) | Live uncertainty — **build your own** if no vendor | 9 | 🔴/🟡 |
| 13 | **Live vote-method availability** (C.1 live) | Validate which Tier-1 states expose method | 9 | 🔴 |
| 14 | **Archived 2022 snapshots** (D.3) | Replay — county / state / synthetic fallback | 7 | 🔴 |

### P3 — Optional / stretch (ship absent under time pressure)
| # | Dataset | Why | Phase | Avail |
|---|---|---|---|---|
| 15 | Historical polling (A.1) | Only if deriving own grades | 4/8 | 🟢 |
| 16 | Expert ratings (F.3) | Prior anchor, tiny weight | 5 | 🟢 |
| 17 | Prediction markets (F.4) | Divergence alert only | 5 | 🟢 |
| 18 | Candidate quality / fundraising (F.2) | Minor fundamentals input | 5 | 🟢 |
| 19 | House district boundaries (C.3) | House module | — | 🟡 |
| 20 | Historical House results (B.2) | House module | — | 🟢 |
| 21 | News / event flags (F.5) | Manual for v1 | 9 | 🟡 |

### The three that actually gate the project
Despite being used late, **#11 (live feed), #13 (live vote-method), and #14 (archived snapshots)**
are the items most likely to change the whole scope. Resolve them **now**, during the gate — they
map directly to pre-coding gate items A.4-1/2/3 in the build plan. Everything in P0/P1 is largely
free and fast; the risk lives entirely in P2.

### One-line sourcing summary
- **Free & easy (get today):** Census ACS, MEDSL, FEC, Senate.gov, NCSL, Ballotpedia, 270toWin, Sabato, Kalshi/Polymarket.
- **Free but fiddly (scrape/clean):** current polling, generic-ballot/approval averages, SoS result pages.
- **Paid / gated (decide early):** AP or DDHQ live feed, Dave Leip's Atlas (cheap), Cook/Inside Elections (skip), archived point-in-time snapshots.
