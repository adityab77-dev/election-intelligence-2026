-- ---------------------------------------------------------------------------
-- 0003_phase6_sim_results
-- Add Phase 6 Monte Carlo summary columns to simulation_results.
-- ---------------------------------------------------------------------------

ALTER TABLE simulation_results ADD COLUMN expected_rep_seats DOUBLE;
ALTER TABLE simulation_results ADD COLUMN expected_dem_seats DOUBLE;
ALTER TABLE simulation_results ADD COLUMN convergence_delta DOUBLE;
ALTER TABLE simulation_results ADD COLUMN influential_states VARCHAR;
