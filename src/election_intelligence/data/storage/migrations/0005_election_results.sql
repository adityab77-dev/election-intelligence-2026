-- ---------------------------------------------------------------------------
-- 0005_election_results (Phase E)
-- Redefine election_results for real result ingestion (denormalised candidate
-- name/party so Wikipedia results need no pre-seeded candidate rows), and add
-- an append-only reporting_snapshots history. Nothing references
-- election_results, so DROP + CREATE is safe.
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
