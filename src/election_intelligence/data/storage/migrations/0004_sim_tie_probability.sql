-- ---------------------------------------------------------------------------
-- 0004_sim_tie_probability
-- Add the 50-50 Senate (tie) probability to the simulation summary. Reporting
-- only; derived from the existing simulation draws.
-- ---------------------------------------------------------------------------

ALTER TABLE simulation_results ADD COLUMN prob_tie DOUBLE;
