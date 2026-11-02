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

## Usage
```bash
election-intelligence init-db            # schema + reference seeds
election-intelligence load-polls         # ingest sample_polls.json (validated)
election-intelligence poll-average        # latest simple average per battleground
election-intelligence poll-average --state GA
```
