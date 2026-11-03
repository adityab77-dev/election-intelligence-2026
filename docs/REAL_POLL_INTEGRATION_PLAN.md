# Real Poll Integration — Automated Ingestion Plan (v2)

> Supersedes the rejected manual-CSV approach. Objective: continuous, automated
> ingestion of real Senate polls into the **existing** `polls` table, with no
> manual uploads, preserving the aggregation engine, forecast engine, Monte
> Carlo simulator, and dashboard unchanged.

## Bottom line
**Step 0 verification (2026-11-02) is complete and the FiveThirtyEight feed is DEAD.**
The decision is therefore: **Wikipedia MediaWiki API is the PRIMARY source**, with a
**last-good committed snapshot for resilience**, refreshed on a schedule by **GitHub
Actions**, flowing into the existing `polls` table. Once configured, zero human touch.
See the Source Verification Report at the end of this document.

## 1. Source evaluation (automation-first)

| Source | Auto-retrievable? | Transport | Format | Party in data? | Grades? | Cost | Durability | Verdict |
|--------|-------------------|-----------|--------|----------------|---------|------|-----------|---------|
| **FiveThirtyEight polls CSV** | ✅ stable URL | HTTPS GET | CSV (long) | ✅ `party` column | ✅ | Free (CC-BY-4.0) | ⚠️ uncertain post-2025 shutdown | Primary **if live** |
| **Wikipedia 2026 Senate articles** | ✅ official API | MediaWiki API | Wikitext/HTML tables | ❌ needs candidate→party map | ❌ | Free (CC-BY-SA) | ✅ durable | Fallback / durable primary |
| **270toWin** | ⚠️ unofficial JSON | HTTPS | JSON | partial | ❌ | Free | ⚠️ | Tertiary |
| **RealClearPolling** | ❌ scrape only | HTML | — | — | ❌ | ToS-restricted | Low | Reject |
| **Decision Desk HQ / commercial APIs** | ✅ (paid) | REST | JSON | ✅ | ✅ | Paid | High | Reject (cost) |
| **"Official polling APIs"** | — | — | — | — | — | — | — | None exist (polls aren't official data) |

Two takeaways: there is no free official polls *API*; the realistic automatable
options are the 538 CSV feed and the Wikipedia API. 538 is far easier and richer
(party + grades in the data); Wikipedia is guaranteed to exist but harder to parse.

## 2. Recommendation (finalized by Step 0)
**Wikipedia MediaWiki API is the primary source; 538 is dropped (dead).** Build the
source-agnostic fetch layer so additional sources can be added later, but implement
the **Wikipedia adapter first**. For resilience, the scheduled job keeps a **last-good
committed snapshot**, so a Wikipedia parse failure or format drift can never break the
live pipeline. Two consequences of losing 538, both handled in the adapter (no engine
change): (a) Wikipedia tables carry **no pollster grades** → ship a **static
pollster-grade table** (last-known public 538 ratings, CC-BY) for the adapter to attach,
else null → existing neutral default weight; (b) party is **not a clean field** → a small,
stable **per-race candidate→party map**.

## 3. Architecture

```
  ┌─ FiveThirtyEight CSV adapter ─┐
  ├─ Wikipedia API adapter ───────┼─ normalize → dedup → validate ─┐
  └─ [future sources] ────────────┘   (common PollSource contract) ▼
                                                   EXISTING PollIngestor
                                                           │
                                                     polls table
                                                           │
   Aggregation ─► Forecast ─► Monte Carlo ─► Dashboard ◄───┘   ALL UNCHANGED
```

New code only in `data/ingestion/` (a `PollSource` interface + adapters + a
normalizer), a `refresh-polls` CLI command, a scheduled GitHub Actions workflow,
and config/docs. Untouched: aggregation, forecast, Monte Carlo, dashboard, the
`polls` table schema, and the `Poll` entity.

## 4. Source-adapter design (common contract)
Each source implements `fetch() -> list[Poll]`:
- **538 adapter:** GET the CSV → filter to U.S. Senate / 2026 / battleground states /
  general → pivot the long format into per-poll DEM/REP `pct` → `margin = dem − rep`.
  Party from the `party` column (no manual map).
- **Wikipedia adapter:** MediaWiki API per race article → parse the standard poll
  tables → resolve party via a small, stable per-race candidate→party map.
- Both emit the existing `Poll` entity; `race_id` via the existing
  `BATTLEGROUND_RACES` state→race mapping.

## 5. Normalization, deduplication, validation
- **Normalization (adapter-side):** margin = `dem_pct − rep_pct`; map source grade
  to the **letter scale the aggregation engine already expects** (or null → neutral
  default weight); `lv/rv/a` → `LV/RV/A`; canonicalize pollster names.
- **Deduplication:** reuse the existing deterministic `poll_id`
  (race + pollster + field_end + population) → re-fetches upsert, never duplicate;
  cross-source dedup via the same key after canonicalization (prefer primary).
- **Validation:** feed reachable; expected columns present (named error on drift);
  sane row counts and pct ranges; staleness warning; bad rows skipped + counted in
  the existing `IngestionReport`.

## 6. Scheduled refresh design
- **Cloud (recommended): GitHub Actions cron.** Every 6–12 h: fetch → normalize →
  validate → dry-run the pipeline (gate) → write a normalized `data/latest_polls.json`
  snapshot → commit **only if changed** → push → Streamlit auto-redeploys and
  recomputes. Resilient: a failed fetch leaves the last good snapshot live.
- **Local: `refresh-polls` CLI + Windows Task Scheduler** (fetch → ingest →
  forecast → simulate on a cron).
- **Lightweight alt:** in-app `st.cache_data(ttl=…)` fetch on view.

## 7. Error handling & resilience
Source down/404/timeout → named `IngestionError`, fall back to secondary, else keep
last snapshot. Schema drift → explicit error. Bad rows skipped. Action failures are
visible (CI red) without degrading the public app. Attribute sources (538 CC-BY-4.0;
Wikipedia CC-BY-SA); store facts, cite provenance.

## 8. Deliverables
1. Step 0 source-verification result.
2. `PollSource` interface.
3. `fivethirtyeight.py` adapter.
4. `wikipedia.py` adapter.
5. Normalizer + pollster canonicalization + cross-source dedup.
6. `refresh-polls` CLI.
7. GitHub Actions scheduled workflow.
8. Config (source selection, interval, battleground filter).
9. Tests (adapter parsing/pivot, normalization, dedup, fallback, end-to-end against a fixture).
10. Docs (README "Automated poll ingestion"; provenance + licensing).

## 9. Fastest path (MVP of this phase)
1. **Step 0 — verify the 538 feed is live for 2026.**
2. Define `PollSource`.
3. Build the primary adapter + normalizer, reusing `PollIngestor`.
4. `refresh-polls` CLI → real polls → forecast → simulate → local dashboard.
5. GitHub Actions cron → real polls flow to the cloud app automatically.
6. Fallback adapter + tests + docs.

**Effort:** ~1–1.5 days if 538 is live; ~2–3 days if Wikipedia is primary.

## 10. Risks
1. 538 feed liveness (#1 — resolved by Step 0).
2. 538 grade format (letter vs numeric) — adapter-side mapping; no engine change.
3. Wikipedia table drift — pinned parser, fails loudly.
4. Independents / RCV — adapter uses the effective two-way.
5. Cloud "Demo Mode" banner — real public data needs a banner edit (dashboard),
   a deliberate small follow-up outside this phase.
6. Commit noise — Action commits only on data change.

## 11. Constraint guarantee
Only `data/ingestion/`, a CLI command, a CI workflow, config, and docs are added.
The `polls` table and everything downstream are unchanged; live polls enter through
the identical validated `PollIngestor` path used today.

---

## Step 0 — Source Verification Report

**Date:** 2026-11-02 · **Method:** live HTTPS fetches via the Windows cert store
(corporate CA trusted), content parsed with pandas / JSON.

### FiveThirtyEight — ❌ NOT VIABLE
| URL | Result |
|-----|--------|
| `projects.fivethirtyeight.com/polls/data/senate_polls.csv` | HTTP 200 but body is **ABC News HTML**, not CSV (feed decommissioned; 538 folded into ABC News after the 2025 shutdown) |
| `projects.fivethirtyeight.com/polls-page/data/senate_polls.csv` | same (HTML) |
| `raw.githubusercontent.com/fivethirtyeight/data/master/polls/senate_polls.csv` | **404** |
| `.../polls/raw_polls.csv` | **404** |

| Requirement check | 538 |
|---|---|
| Feed accessible | ⚠️ URL responds but serves a webpage, not data |
| 2026 Senate rows | ❌ none (no CSV) |
| Recent dates | ❌ n/a |
| Party info | ❌ n/a |
| Grade info | ❌ n/a |

### Wikipedia MediaWiki API — ✅ VIABLE (new primary)
`action=parse&prop=wikitext` for the 2026 Senate race articles (GA, TX, NC):

| Article | Result |
|---|---|
| 2026 U.S. Senate election in Georgia | 200 · 102 KB wikitext · 25 wikitables · Opinion-polling section present |
| …in Texas | 200 · 344 KB · 37 wikitables · polling section present |
| …in North Carolina | 200 · 109 KB · 16 wikitables · polling section present |

| Requirement check | Wikipedia |
|---|---|
| Feed accessible | ✅ official API, free, CC-BY-SA |
| 2026 Senate rows | ✅ Opinion-polling tables per race |
| Recent dates | ✅ tables carry "Date(s) administered" (validated per-row at parse) |
| Party info | ⚠️ not a clean field — needs a per-race candidate→party map |
| Grade info | ❌ not present — supply via a static grade table (see §2) |

### Final decision
- **Primary source: Wikipedia MediaWiki API.** 538 dropped.
- **Resilience:** last-good committed snapshot (parse failure / format drift can't break the live app).
- **Grades:** shipped static pollster-grade table (adapter attaches), else neutral default — **no aggregation-engine change**.
- **Party:** small stable per-race candidate→party map in the adapter.

### Updated effort & deliverables delta
- Effort revised to **~2–3 days** (Wikipedia table parsing is more work than a CSV).
- Added deliverables: **per-race candidate→party map** and **static pollster-grade table**.
- Risk #1 (538 liveness) is **resolved: dead** — removed from the open-risk list.
- Everything downstream of the `polls` table remains unchanged, as specified.

---

## Deeper Source Analysis (provenance-first)

### The core tradeoff
"Closest to the original source" and "automatable + sustainable + legal" pull in opposite
directions — which is why aggregators exist. Pollsters publish toplines as **PDF crosstabs +
HTML press releases** in ~15 bespoke formats with no common schema, API, or feed (best
provenance, worst automation). Aggregators collect those into structured form (one hop
removed, transcription risk, but the only thing machine-ingestible at scale). "Direct from
every pollster, automated, solo, sustainably" is structurally impractical.

### Inventory & ranking (1–5, 5 best)

| Source | Timeliness | Reliability | Automation | Sustainability | Legal | Verdict |
|--------|:--:|:--:|:--:|:--:|:--:|--------|
| **DDHQ polling API** (commercial) | 5 | 5 | 5 | 4 | 5 | Best overall — licensed, near-direct; cost is the only con |
| **Direct pollster sites** | 5 | 5 | 1 | 3 | 4 | Purest provenance, impractical to automate |
| **ABC/538-successor data** | ? | 5 | ? | ? | ? | Verify — 538 dataset may live on under ABC |
| **RealClearPolling** | 5 | 4 | 2 | 3 | 2 | Near-direct but no API, ToS-restricted, fragile |
| **Silver Bulletin** | 4 | 5 | 2 | 4 | 2 | Paywalled, no data API |
| **270toWin** | 4 | 4 | 3 | 2 | 2 | Undocumented JSON; unofficial |
| **Open datasets (GitHub)** | 3 | 3 | 4 | 2 | 4 | Verify a maintained 2026 one exists |
| **Daily Kos Elections sheet** | 4 | 4 | 3 | 3 | 3 | Public sheet; semi-structured |
| **Wikipedia API** (rejected as primary) | 3 | 4 | 4 | 5 | 5 | Durable & legal, two hops from source |
| **Roper / academic** | 1 | 5 | 2 | 5 | 3 | Archival, not live-cycle |
| **AP / results APIs** | — | — | — | — | — | Results, not polls — out of scope |

### Recommended posture for a serious platform
A tiered, provenance-anchored architecture (not a single scraper):
1. **Primary backbone:** a licensed machine-readable feed (**DDHQ or equivalent**) — the only
   option strong on all five axes at once; cost is the tradeoff.
2. **Provenance layer:** store each poll's original **pollster-release URL** (`Poll.url` exists);
   anchor toplines to the pollster's own release where retrievable.
3. **Reconciliation + resilience:** a secondary free source (Wikipedia/RCP) as cross-check and
   gap-filler (the spec's dual-source rule), plus a last-good committed snapshot.
4. **Grades:** ship a static pollster-grade table (archived 538 ratings, CC) — no engine change.

If a paid feed is off the table, the best *free* posture is a near-direct aggregator for
coverage + original-URL provenance + Wikipedia reconciliation — materially lower quality,
which is the honest cost of "free."

---

## Step 0.5 — Probe Results & Final Source Recommendation

**Date:** 2026-11-02 · **Method:** live HTTPS probes (Windows cert store) of candidate sources.

### Probe findings

| Probe | Result |
|-------|--------|
| **ABC / 538-successor** | ❌ Dead. The 538 polls page returns 365 KB of ABC HTML with **no embedded data endpoint** (no `.csv`/`.json`/`/polls/data/`/`__NEXT_DATA__`). The `fivethirtyeight/data` GitHub repo is **frozen since 2025-02-25** and its `/polls` dir holds only historical *presidential* averages — no Senate, no 2026. |
| **270toWin** | ❌ No machine-readable feed. The 2026 Senate page's only inline endpoints are Google Maps and a newsletter PHP; poll data is server-rendered HTML → scraping only (unofficial, fragile). |
| **Open GitHub datasets** | ❌ Not authoritative. Search returned only **hobby repos (0 stars, just-created election-night trackers)**; none are maintained, sourced, or sustainable. |
| **DDHQ** | ✅ **Viable.** `docs.decisiondeskhq.com` exposes a documented **v4/v5 REST API** with OAuth2 auth and **polling endpoints**. |

### DDHQ API — details (deliverable #4)
- **Availability:** live, documented API (`docs.decisiondeskhq.com`), with a **testing environment**.
- **Auth / integration:** OAuth2 client-credentials → bearer token (`POST /api/v4/oauth/token`), then
  GET JSON. Polling surface includes `/api/v4/polls/base_data/{pollsters,sponsors,types,modes,internals}`
  plus race/results endpoints (`/race/{id}`, `/races`, `/race-calls`, `/pulse`, `/balance_of_power`).
  Clean, machine-readable, provenance-rich (pollster/sponsor/mode metadata).
- **Cost:** subscription; signals for a **trial** tier are present, but **pricing is gated** (login/contact) —
  not publicly listed. Obtaining it requires the account holder to **request access/trial** (the one step
  only you can take).
- **Not yet confirmed (needs credentials):** exact 2026 Senate race-level poll coverage, per-poll field
  granularity (candidate pct / party / dates / population), grade equivalents, and price — all verifiable
  once trial credentials are in hand (a short "Step 0.6" against the live endpoints).

### Final recommendation
**Primary: the DDHQ API** — it is the only source that is simultaneously near-direct, highest-quality,
fully automatable (OAuth2 + REST JSON), sustainable, and legally licensed, which matches the stated
"provenance-first, quality over cost" priority. **Secondary (reconciliation + gap-fill + resilience):**
the Wikipedia MediaWiki API plus the last-good committed snapshot. **Grades:** static pollster-grade
table if DDHQ's metadata lacks a usable grade — no engine change.

**Decision gate (one external action):** obtain DDHQ **trial credentials**, then run Step 0.6 to confirm
Senate coverage, fields, and price.
- If DDHQ confirms out → **DDHQ primary**, Wikipedia secondary. *(Recommended path.)*
- If DDHQ is unaffordable/insufficient → **Wikipedia primary** (prior decision), snapshot + static grades.

Ruled out as primary by probes: 538/ABC (dead), 270toWin (no feed), hobby GitHub datasets (not
sustainable), RealClearPolling (no API, ToS), Silver Bulletin (paywalled, no API).

### Architecture (unchanged by this result)
Pluggable `PollSource` → the chosen primary adapter (DDHQ or Wikipedia) → normalize → dedup →
existing `PollIngestor` → `polls` table → untouched aggregation/forecast/MC/dashboard. The
provenance layer stores each poll's original source URL regardless of primary.

