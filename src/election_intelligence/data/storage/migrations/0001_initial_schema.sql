-- ---------------------------------------------------------------------------
-- 0001_initial_schema
-- Core Phase 2 entities for the 2026 Senate Control Intelligence System.
-- DuckDB dialect. JSON-shaped columns are stored as VARCHAR (JSON text) and
-- (de)serialised in the repository layer, to avoid any JSON-extension coupling.
-- ---------------------------------------------------------------------------

-- Enum types (strong typing at the storage layer) -----------------------------
CREATE TYPE party AS ENUM ('DEM', 'REP', 'IND', 'LIB', 'GRN', 'OTH');
CREATE TYPE counting_rule AS ENUM ('plurality', 'majority_runoff', 'ranked_choice');
CREATE TYPE poll_population AS ENUM ('LV', 'RV', 'A', 'V');
CREATE TYPE sim_regime AS ENUM ('pre_election', 'live');
CREATE TYPE run_status AS ENUM ('pending', 'running', 'completed', 'failed');

-- states ----------------------------------------------------------------------
CREATE TABLE states (
    state_code      VARCHAR PRIMARY KEY,
    name            VARCHAR NOT NULL,
    time_zone       VARCHAR NOT NULL,
    poll_close_utc  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- senate_races ----------------------------------------------------------------
CREATE TABLE senate_races (
    race_id             VARCHAR PRIMARY KEY,
    state_code          VARCHAR NOT NULL REFERENCES states(state_code),
    seat_class          VARCHAR,
    is_special          BOOLEAN NOT NULL DEFAULT FALSE,
    office              VARCHAR NOT NULL DEFAULT 'US Senate',
    counting_rule       counting_rule NOT NULL DEFAULT 'plurality',
    incumbent_party     party,
    expert_rating       VARCHAR,
    recount_margin_pct  DOUBLE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- candidates ------------------------------------------------------------------
CREATE TABLE candidates (
    candidate_id   VARCHAR PRIMARY KEY,
    race_id        VARCHAR NOT NULL REFERENCES senate_races(race_id),
    name           VARCHAR NOT NULL,
    party          party NOT NULL,
    is_incumbent   BOOLEAN NOT NULL DEFAULT FALSE,
    caucuses_with  party,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- polls -----------------------------------------------------------------------
CREATE TABLE polls (
    poll_id               VARCHAR PRIMARY KEY,
    race_id               VARCHAR NOT NULL REFERENCES senate_races(race_id),
    pollster              VARCHAR NOT NULL,
    pollster_grade        VARCHAR,
    field_start           DATE,
    field_end             DATE NOT NULL,
    sample_size           INTEGER,
    population            poll_population,
    mode                  VARCHAR,
    sponsor               VARCHAR,
    margin_dem_minus_rep  DOUBLE NOT NULL,
    house_effect_adj      DOUBLE,
    url                   VARCHAR,
    ingested_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- poll_aggregates -------------------------------------------------------------
CREATE TABLE poll_aggregates (
    aggregate_id           VARCHAR PRIMARY KEY,
    race_id                VARCHAR NOT NULL REFERENCES senate_races(race_id),
    as_of                  DATE NOT NULL,
    mean_margin            DOUBLE NOT NULL,
    std_error              DOUBLE,
    n_polls                INTEGER NOT NULL DEFAULT 0,
    effective_sample_size  DOUBLE,
    method                 VARCHAR NOT NULL DEFAULT 'v1',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (race_id, as_of, method)
);

-- simulation_runs -------------------------------------------------------------
-- One row per worker tick. (inputs_hash, random_seed, code_version) make every
-- downstream output reproducible.
CREATE TABLE simulation_runs (
    run_id         VARCHAR PRIMARY KEY,
    regime         sim_regime NOT NULL,
    n_simulations  INTEGER NOT NULL,
    random_seed    BIGINT NOT NULL,
    inputs_hash    VARCHAR NOT NULL,
    code_version   VARCHAR,
    trigger        VARCHAR,
    status         run_status NOT NULL DEFAULT 'pending',
    notes          VARCHAR,
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- state_forecasts -------------------------------------------------------------
CREATE TABLE state_forecasts (
    forecast_id    VARCHAR PRIMARY KEY,
    run_id         VARCHAR NOT NULL REFERENCES simulation_runs(run_id),
    race_id        VARCHAR NOT NULL REFERENCES senate_races(race_id),
    mean_margin    DOUBLE NOT NULL,
    std_margin     DOUBLE NOT NULL,
    prob_dem_win   DOUBLE,
    prob_rep_win   DOUBLE,
    prob_over_50   DOUBLE,
    drivers        VARCHAR,               -- JSON text
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, race_id)
);

-- simulation_results ----------------------------------------------------------
-- Chamber-level summary; one row per run (not per draw).
CREATE TABLE simulation_results (
    run_id             VARCHAR PRIMARY KEY REFERENCES simulation_runs(run_id),
    prob_rep_control   DOUBLE NOT NULL,
    prob_dem_control   DOUBLE NOT NULL,
    prob_undetermined  DOUBLE NOT NULL DEFAULT 0,
    mc_std_error       DOUBLE,
    rep_seats_median   INTEGER,
    rep_seats_p10      INTEGER,
    rep_seats_p90      INTEGER,
    seat_histogram     VARCHAR,           -- JSON text
    paths              VARCHAR,           -- JSON text
    conditionals       VARCHAR,           -- JSON text
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- election_results ------------------------------------------------------------
-- Reported vote snapshots per candidate (live night). Append-only; snapshots
-- failing integrity checks are kept with quarantined = TRUE.
CREATE TABLE election_results (
    result_id          VARCHAR PRIMARY KEY,
    race_id            VARCHAR NOT NULL REFERENCES senate_races(race_id),
    candidate_id       VARCHAR NOT NULL REFERENCES candidates(candidate_id),
    votes              BIGINT NOT NULL DEFAULT 0,
    pct_expected_vote  DOUBLE,
    is_called          BOOLEAN NOT NULL DEFAULT FALSE,
    source             VARCHAR NOT NULL,
    reported_at        TIMESTAMPTZ NOT NULL,
    quarantined        BOOLEAN NOT NULL DEFAULT FALSE,
    quarantine_reason  VARCHAR,
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Secondary indexes -----------------------------------------------------------
CREATE INDEX idx_senate_races_state ON senate_races(state_code);
CREATE INDEX idx_candidates_race ON candidates(race_id);
CREATE INDEX idx_polls_race ON polls(race_id);
CREATE INDEX idx_poll_aggregates_race ON poll_aggregates(race_id);
CREATE INDEX idx_state_forecasts_run ON state_forecasts(run_id);
CREATE INDEX idx_state_forecasts_race ON state_forecasts(race_id);
CREATE INDEX idx_election_results_race ON election_results(race_id);
