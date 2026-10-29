# Data directory

Follows a conventional layered layout. The folders are tracked (via `.gitkeep`)
but their contents are gitignored — data is never committed.

| Folder | Contents |
|--------|----------|
| `raw/` | Immutable source data exactly as ingested. Never edited in place. |
| `interim/` | Intermediate, partially-transformed data. |
| `processed/` | Clean, analysis-ready data and the DuckDB database file. |
| `external/` | Third-party reference data (boundaries, demographics, etc.). |
