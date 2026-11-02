-- ---------------------------------------------------------------------------
-- 0002_phase5_state_forecasts
-- Redefine state_forecasts for the Phase 5 per-state forecast distribution.
-- The Phase 1/2 placeholder (run-linked, with win-probability columns) is
-- replaced by the margin distribution that Phase 5 produces and Phase 6
-- Monte Carlo will consume. Nothing references state_forecasts, so DROP is safe.
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS state_forecasts;

CREATE TABLE state_forecasts (
    forecast_id       VARCHAR PRIMARY KEY,
    race_id           VARCHAR NOT NULL REFERENCES senate_races(race_id),
    state_code        VARCHAR,
    mean_margin       DOUBLE NOT NULL,
    sigma             DOUBLE NOT NULL,
    confidence_level  VARCHAR NOT NULL,
    poll_count        INTEGER NOT NULL DEFAULT 0,
    forecast_date     DATE NOT NULL,
    method            VARCHAR NOT NULL DEFAULT 'poll_only_v1',
    inputs_hash       VARCHAR NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (race_id, forecast_date, method)
);

CREATE INDEX idx_state_forecasts_race ON state_forecasts(race_id);
