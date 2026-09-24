# Changelog

## Unreleased -- Post-v1.0.0 upgrade work

### Phase 1: Real analytical SQL (2026-09-24)
`sql/analysis/*.sql` was thin -- `bottlenecks.sql` was the only file using a window function,
despite docs claiming LAG/LEAD/RANK/rolling metrics (v1.0.0's own "known limitations" already
named this: "`sql/analysis/*.sql` still stubs"). Closed:

- 9 new/rewritten files, run live against Neon, not just written: `waiting_time_lag.sql` (LAG),
  `variant_ranking.sql` (RANK/DENSE_RANK, two rankings -- volume and breach rate),
  `rolling_sla_breach_rate.sql` (RANGE window frame over a calendar interval, per category),
  `monthly_cohort_breach_trend.sql` (cumulative SUM() OVER), `supplier_quartiles.sql`
  (NTILE/PERCENT_RANK), `slowest_stage_per_case.sql` (FIRST_VALUE/LAST_VALUE),
  `running_event_count.sql` (ROW_NUMBER + a correlated subquery, with the reasoning for why a
  window function doesn't fit that specific question), `category_relative_cycle_time.sql`
  (PERCENT_RANK/z-score), `rework_detection.sql` (window COUNT, no self-join).
- 3 real bugs found by running these, not by inspection: `COUNT(DISTINCT ...) OVER (...)`
  doesn't exist in Postgres; `ROUND(double precision, integer)` doesn't exist; `QUALIFY`
  (Snowflake/BigQuery syntax) doesn't exist either. All three fixed with the correct Postgres
  idiom, documented in the file where they were found.
- A 4th, more consequential bug in `scripts/setup_database.py`'s migration runner (naive
  `split(";")` breaks on a semicolon inside a `--` comment) surfaced real schema drift: none of
  `sql/schema/002_create_indexes.sql`'s indexes had ever actually been applied to the live
  database. Fixed and re-applied for real, verified via `pg_indexes`.
- `EXPLAIN ANALYZE` before/after a new `(case_id, timestamp)` composite index: the query plan
  changed (Seq Scan -> Index Scan) but measured execution time did not (58.4ms -> 59.2ms) at
  this table's current 32K-row size -- reported as a real negative result, not a speedup.
- Seeded-database test suite (`tests/test_sql_analysis_live.py`): no local Postgres/Docker is
  available in this environment, so it seeds a real, throwaway Postgres *database* (not just a
  schema -- these files hardcode `staging.`/`analytics.` schema names, which already exist in
  production on the same server) on the same Neon project, with hand-designed fixture data whose
  correct answers are known in advance, runs all 10 files against it, and drops the database in
  a `finally` block. Opt-in (`RUN_LIVE_SQL_TESTS=1`) since it needs real DB credentials with
  `CREATE DATABASE` privilege that CI does not have configured.
- Full writeup: [`docs/sql-window-functions.md`](docs/sql-window-functions.md).

Remaining, explicitly deferred, larger phases (dbt transformation layer, Prefect orchestration,
feature-level drift, a sequence model for early prediction, an intervention/ROI simulation
layer, README rewrite) are tracked separately -- not attempted in this same pass, since each is
a multi-day scope of its own and rushing them would violate this project's own honesty standard
(every number reproducible, negative results reported not tuned away).

## v1.0.0 -- Freeze

Everything through Phase 30 (Performance & cost pass) is complete, tested, and audited. This is
the frozen baseline -- no further feature work happens against this version. New ideas go in
`FUTURE_IMPROVEMENTS.md`, not directly into the code.

**To actually tag this once the repo is under real git version control:**
```
git init   # if not already
git add -A && git commit -m "v1.0.0 -- Operations Performance"
git tag -a v1.0.0 -m "Frozen baseline after Phases 1-30"
```

### What's in v1.0.0
- Full ETL pipeline: contract-checked, validated, cleaned ingestion of BPI Challenge 2019 data,
  idempotent, audit-logged (`pipeline_runs`)
- Process analytics: cycle time, bottlenecks, variants, conformance, rework, root-cause,
  supplier scorecards -- every metric independently hand-verified against a golden dataset
  (Phase 27), not just unit-tested
- SLA-risk ML model: time-based split, lightweight explainability, documented model card
- FastAPI analytics layer (8 endpoints) consumed by both a local dashboard spec and the
  companion `operations-assistant` project
- BigQuery migration path with a real Postgres-vs-BigQuery comparison
- Least-privilege DB roles, input-validated CORS, structured JSON logging
- 65 tests, all passing, including a real correctness audit and 3 end-to-end business scenarios
- CI running the full suite on every push

### Real bugs found and fixed during the build (kept for the record, not scrubbed out)
1. `_count_out_of_order` sorted before diffing, silently defeating the check it implemented
2. A pandas-3.0 dtype-check incompatibility in the data contract
3. `conformance.py`'s out-of-order check never correctly handled allowed repeated activities --
   `allowed_repeats` silently never worked for conformance checking, only rework detection
   (found by Phase 27's hand-verified golden dataset)
4. `rework_by_case` was ~98x slower than necessary due to a Python-level loop where a single
   vectorized groupby would do (found by Phase 30's benchmark)
5. **Every documented script invocation was broken from Phase 0 onward** -- `python
   scripts/run_pipeline.py` (exactly what the README said to run) failed on the first import,
   for anyone, the whole time. Found by Phase 30 actually running the benchmark command as a
   real user would, not by code inspection.
6. Two smaller Phase 25 audit findings: an inconsistent import path, an undeclared direct
   dependency (`pydantic`)

### Known limitations, stated plainly (not gaps to be embarrassed by -- see FUTURE_IMPROVEMENTS.md)
- SHAP-based explainability not implemented (lightweight approximation only)
- `sql/analysis/*.sql` still stubs -- the Python analytics have SQL equivalents planned, not built
- Dashboard is a documented build spec, not an actual built `.pbix`/Looker file
- No API authentication
- `check_conformance` has the same performance shape `rework_by_case` had before its Phase 30
  fix -- not urgent at current scale, documented in `docs/performance-notes.md`
- Never run against a live Postgres instance or real BigQuery project in this environment
