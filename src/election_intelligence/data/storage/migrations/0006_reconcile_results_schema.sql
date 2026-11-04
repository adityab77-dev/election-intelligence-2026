-- ---------------------------------------------------------------------------
-- 0006_reconcile_results_schema (Phase E hardening)
-- Migration versions are tracked by number only, so an earlier deployment that
-- applied an older 0005 keeps its (now-drifted) election_results /
-- reporting_snapshots schema forever -- e.g. a persisted Streamlit Cloud DB
-- missing reporting_snapshots.created_at, which breaks the dashboard's
-- "ORDER BY reported_at DESC, created_at DESC" query. Both tables are
-- append-only roll-ups rebuilt from live feeds on every refresh, so dropping
-- and recreating them with the current schema is safe and self-healing.
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS election_results;

CREATE TABLE election_results (
    result_id          VARCHAR PRIMARY KEY,
    race_id            VARCHAR NOT NULL REFERENCES senate_races(race_id),
    state_code         VARCHAR,
    county_fips        VARCHAR,
    candidate_name     VARCHAR NOT NULL,
    party              party,
    votes              BIGINT NOT NULL DEFAULT 0,
    vote_share         DOUBLE,
    percent_reporting  DOUBLE,
    is_called          BOOLEAN NOT NULL DEFAULT FALSE,
    source             VARCHAR NOT NULL,
    reported_at        TIMESTAMPTZ NOT NULL,
    quarantined        BOOLEAN NOT NULL DEFAULT FALSE,
    quarantine_reason  VARCHAR,
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_election_results_race ON election_results(race_id);

DROP TABLE IF EXISTS reporting_snapshots;

-- Append-only race-level roll-up, one row per fetch (the night's history).
CREATE TABLE reporting_snapshots (
    snapshot_id        VARCHAR PRIMARY KEY,
    race_id            VARCHAR NOT NULL REFERENCES senate_races(race_id),
    source             VARCHAR NOT NULL,
    reported_at        TIMESTAMPTZ NOT NULL,
    percent_reporting  DOUBLE NOT NULL DEFAULT 0,
    total_votes        BIGINT NOT NULL DEFAULT 0,
    dem_votes          BIGINT NOT NULL DEFAULT 0,
    rep_votes          BIGINT NOT NULL DEFAULT 0,
    other_votes        BIGINT NOT NULL DEFAULT 0,
    margin             DOUBLE,
    leader_party       party,
    is_called          BOOLEAN NOT NULL DEFAULT FALSE,
    called_party       party,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (race_id, source, reported_at)
);

CREATE INDEX idx_reporting_snapshots_race ON reporting_snapshots(race_id);
