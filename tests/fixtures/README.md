# Test fixtures

Sample data used by the test suite.

- **Phase 1 (now):** this directory and its `FIXTURES_DIR` anchor only.
- **Phase 3:** a small synthetic "golden-path" dataset (a handful of races, units,
  and polls) so the aggregation, forecast, and simulation engines can be built and
  tested before real data arrives.
- **Phase 7:** recorded point-in-time snapshots for the replay framework live here
  (or are generated synthetically — see `REFERENCE_DATA_CHECKLIST.md` D.3).

Fixtures are committed (they are small and non-sensitive); real downloaded data is
never committed — it belongs under the gitignored `data/` tree.
