# Election Intelligence 2026

A Python platform for election forecasting and analysis.

> **Status:** Scaffold. The project structure, configuration, logging, storage
> and LLM wrappers, and test harness are in place. Forecasting logic is **not**
> implemented yet — the model layer defines interfaces only.

## Stack

- **Python 3.12**
- **DuckDB** — embedded analytical database / storage layer
- **Pandas · NumPy** — data manipulation
- **Statsmodels** — statistical modeling (forecasting, to come)
- **Streamlit** — interactive dashboard
- **Claude API** (`anthropic`) — narrative analysis and LLM-assisted insight
- **pytest** — testing
- **Pydantic Settings · Ruff · mypy** — configuration, linting, type-checking

## Architecture

The codebase uses a `src/` layout and a layered architecture. Each layer
depends only on the ones below it, which keeps responsibilities clear and the
pieces independently testable and replaceable.

```
election-intelligence-2026/
├── config/                      # Reference config (logging.yaml) + docs
├── data/                        # Layered data lake (gitignored contents)
│   ├── raw/ interim/ processed/ external/
├── logs/                        # Rotating log files (gitignored)
├── notebooks/                   # Exploratory analysis
├── src/
│   └── election_intelligence/
│       ├── __init__.py
│       ├── cli.py               # `election-intelligence` console entry point
│       ├── exceptions.py        # Project-wide exception hierarchy
│       ├── config/              # Typed, layered settings (Pydantic)
│       ├── utils/               # Logging and shared helpers
│       ├── data/
│       │   ├── ingestion/       # DataSource interface + source readers
│       │   └── storage/         # DuckDB client wrapper
│       ├── models/              # ForecastModel interface (logic TBD)
│       ├── llm/                 # Claude API client wrapper
│       ├── analysis/            # Cross-layer analytical workflows
│       └── dashboard/           # Streamlit app
└── tests/
    ├── conftest.py              # Shared, isolating fixtures
    ├── unit/                    # Fast, isolated tests
    └── integration/             # Tests touching DuckDB / filesystem
```

### Dependency direction

```
dashboard ─┐
analysis  ─┼──► models ──► data ──► config / utils / exceptions
llm       ─┘
```

Nothing in the lower layers imports from the higher ones.

## Getting started

```bash
# 1. Create and activate a virtual environment (Python 3.12)
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell)
# source .venv/bin/activate     # macOS / Linux

# 2. Install the project (editable) with dev tooling
pip install -e ".[dev]"

# 3. Configure
copy .env.example .env          # Windows
# cp .env.example .env            # macOS / Linux
# then edit .env and set EI_CLAUDE__API_KEY to use the LLM layer
```

## Common commands

```bash
# Show resolved configuration
election-intelligence info

# Launch the dashboard
streamlit run src/election_intelligence/dashboard/app.py

# Run the test suite
pytest                      # everything
pytest -m unit              # fast unit tests only
pytest -m integration       # integration tests

# Lint, format, type-check
ruff check .
ruff format .
mypy
```

## Configuration

All settings are typed and loaded from (in order of precedence) environment
variables, a local `.env` file, then defaults. See [`config/README.md`](config/README.md)
and [`src/election_intelligence/config/settings.py`](src/election_intelligence/config/settings.py).

## Logging

Logging is configured centrally in
[`src/election_intelligence/utils/logging_config.py`](src/election_intelligence/utils/logging_config.py).
Call `configure_logging()` once at an entry point, then `get_logger(__name__)`
anywhere. Set `EI_LOGGING__JSON_FORMAT=true` for structured JSON logs.

## Design principles

- **Maintainability** — small, single-responsibility modules; one source of
  truth for configuration and logging.
- **Reliability** — typed settings validated at load time, isolated test
  fixtures, a consistent exception hierarchy, idempotent setup routines.
- **Clean architecture** — strict layering; abstract interfaces
  (`DataSource`, `ForecastModel`) decouple callers from implementations.
- **Extensibility** — new data sources, models and analyses plug in by
  implementing an interface; no changes required to existing layers.
