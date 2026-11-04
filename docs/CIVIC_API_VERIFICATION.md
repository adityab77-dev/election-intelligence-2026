# Source Verification Report — "civicAPI" (Google Civic Information API)

Prepared 2026-11-03. **Investigation only — no code.** Question: can civicAPI replace Wikipedia
as the election-**results** source?

## What it is (empirically confirmed)
"civicAPI" = the **Google Civic Information API** (`civicinfo.googleapis.com/civicinfo/v2`). Its own
discovery document describes it as:

> "Provides polling places, early vote locations, contest data, election officials, and government
> representatives for U.S. residential addresses."

Its **only** methods are:
- `divisions.queryDivisionByAddress`, `divisions.search`
- `elections.voterInfoQuery` (where to vote, what's on the ballot, candidates, election officials)
- `elections.electionQuery` (the list of upcoming elections)

Endpoints are **API-key-gated** (probed → HTTP 403 without a key). The `vote`/`precinct` field keys
in the schema refer to **voting locations** (early-vote sites, polling precincts), not vote counts.

## Task 1 — can it provide live results?

| Required field | Google Civic API | Evidence |
|----------------|:---:|---|
| 2026 Senate **race coverage** | ⚠️ ballot/contest info only | `voterInfoQuery` returns contests + candidates, no tallies |
| **Vote totals** | ❌ **Not provided** | No results/tally endpoint or field |
| **Vote share %** | ❌ **Not provided** | — |
| **Percent reporting** | ❌ **Not provided** | No `reporting`/`percent` result field |
| **Race calls** | ❌ **Not provided** | No `winner`/`called` field |
| **Update frequency** | ❌ n/a | It is not a live-results feed |

**It carries no election results at all.** Google's API is for *voter information* (where/how to vote,
who is on the ballot), not vote counts. (Separately: Google has been **retiring** parts of this API —
the `representatives` endpoint was shut down in 2025 — so even its civic data is shrinking.)

## Task 2 — proof-of-concept adapter
**Not feasible.** A `CivicAPIResultsSource` cannot be built, because the API returns no results data
to parse. There is nothing to map to `ReportingSnapshot` / `ElectionResult`.

## Task 3 — civicAPI vs Wikipedia (as a results source)

| Dimension | Google Civic API | WikipediaResultsSource |
|-----------|---|---|
| **Freshness** | n/a — no results | Lags real counting (editor-transcribed), but does update |
| **Completeness** | **Zero** results data | Vote totals + shares once editors populate the general-election table |
| **Reliability** | API is reliable **but for voter info, not results**; partially deprecated | Community-maintained; format-fragile but real |
| **Ease of integration** | Key required; irrelevant — no results | Already built and working |

## Task 4 — recommendation
**Do NOT replace WikipediaResultsSource with a civicAPI source.** The Google Civic Information API is a
voter-information API and provides **no vote totals, vote share, percent reporting, or race calls**, so
it cannot serve as an election-results source under any configuration. Keep **Wikipedia** as the free
results source (accepting its lag), and treat the **DDHQ Results API** (enterprise, OAuth — see
`PHASE_E_ARCHITECTURE.md`) as the upgrade path for real-time, uniform results with official calls.

> If "civicAPI" referred to a *different* product (not Google's Civic Information API), say which one
> and I'll verify it the same way — but no free civic/voter-info API provides live vote results; those
> come only from AP, DDHQ, or state SoS feeds.
