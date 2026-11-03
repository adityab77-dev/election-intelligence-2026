# Polling ingestion (Phase 3, MVP)

Minimal, battleground-only polling ingestion. Not a generalized framework.

## Files
- `polls.py` — validation, the `PollIngestor`, and descriptive queries
  (`simple_polling_average`, `latest_poll`). No forecasting logic.
- `sample_polls.json` — seed polling data for MVP development.

## ⚠️ `sample_polls.json` is SYNTHETIC

The values in `sample_polls.json` are **fabricated development data**, not real
published polls. Pollster names are used only as realistic categorical labels;
the margins, sample sizes and dates were made up to exercise the pipeline and
dashboard. **Do not treat these as actual polling results.** Real polling data
must be sourced per `REFERENCE_DATA_CHECKLIST.md` (A.2) before any real forecast.

## Real polls — Wikipedia source (Phase A)

Automated, real polling is ingested from the **Wikipedia MediaWiki API** (CC-BY-SA)
via a pluggable source layer. See `docs/REAL_POLL_INTEGRATION_PLAN.md` for why
Wikipedia is the V1 source (538 is dead; DDHQ API is a future enterprise upgrade).

- `sources/base.py` — the `PollSource` contract (`fetch() -> list[Poll]`); DDHQ can
  later drop in without changes downstream of the `polls` table.
- `sources/wikipedia.py` — fetches each battleground article, selects the current
  **general-election** D-vs-R poll table (newest matchup), and normalizes each row.
- `party_mapping.py` — candidate → party from the `(D)`/`(R)` column suffix.
- `pollster_grades.py` — static grade table (Wikipedia carries no grades); unknown
  pollsters fall back to the aggregation engine's neutral default weight.
- `normalization.py` — date-range / sample / pct / pollster-name parsing.

Deduplication reuses the existing deterministic `poll_id`
(`race + pollster + field_end + population`), so refreshes **upsert**. Validation
reuses `validate_poll`. **No `polls` schema change** — real polls use the same table.

### Usage
```bash
election-intelligence init-db                    # schema + reference seeds
election-intelligence load-polls --source wikipedia   # ingest REAL polls (all 8 battlegrounds)
election-intelligence poll-average                # weighted aggregates from real polls
election-intelligence load-polls                 # (synthetic sample, for offline/demo)
election-intelligence poll-average --state GA
```

> Behind a TLS-intercepting proxy, set `SSL_CERT_FILE` to your CA bundle so the live
> fetch validates (not needed on Streamlit Cloud / GitHub Actions).
