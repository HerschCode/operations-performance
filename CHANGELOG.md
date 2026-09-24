# Changelog

## Unreleased -- Post-v1.0.0 upgrade work

### Phase 4: Feature drift + retrain loop (2026-09-24)
- `src/ml/feature_drift.py`: per-feature PSI on raw inputs, baselines saved in model metadata at
  train time (`config/drift.yaml` thresholds). `scripts/backfill_feature_baselines.py` added them to
  the deployed model without retraining.
- New `GET /health/drift/features` (additive; existing endpoints unchanged) + dashboard section.
- `retrain_trigger` gains a feature-drift reason; the Prefect flow gains `retrain_gate_task`
  (`force_retrain` option). Simulated-drift tests prove it fires and that calm data skips training.
- Honest finding: on the static replay data 9/10 features alert (train-vs-later-period gap);
  thresholds not tuned. See `docs/feature-drift.md`.

### Phase 3: Prefect orchestration (2026-09-24)
No orchestration existed beyond a bare GitHub Actions cron calling one script
(`retrain-check.yml`). Added `flows/pipeline_flow.py`: ingest -> validate -> dbt build -> train
-> evaluate/register -> report, each step reusing existing, already-tested code rather than
duplicating it (`scripts/run_pipeline.py::run()`, `src/cleaning/data_quality.py`, Phase 2's
`dbt build`, `src/ml/train.py::train_models()`/`save_best_model()`).

- **Register only if the candidate beats the deployed model, verified against a real live run,
  not just asserted:** `config/orchestration.yaml`'s `min_roc_auc_improvement` (0.005) gates
  `save_best_model()`. First real end-to-end run: candidate random_forest scored 0.9888 vs the
  already-deployed model's 0.9857 (+0.0031, below the margin) -- correctly kept the deployed
  model rather than replacing it on a difference too small to trust, matching the paired
  significance finding in `docs/statistical-significance.md`.
- **A real integration conflict, found by running the flow, not by inspection:**
  `ingest_task`'s raw-table replace (`DROP TABLE staging.events`) failed once Phase 2's dbt
  views existed on top of it -- "other objects depend on it". Fixed by sequencing: `ingest_task`
  now drops the dbt-managed schemas first, and `dbt_build_task` (which runs immediately after in
  the same flow) fully rebuilds them.
- **Acceptance criterion proven directly, not just asserted:** "a failed DQ check stops the flow
  before training" -- `tests/test_pipeline_flow.py::test_failed_dq_check_stops_the_flow_before_training`
  runs the real flow function with `validate_task` raising, and asserts
  `dbt_build_task`/`train_task`/`evaluate_and_register_task`/`report_task` are never called.
- A real Prefect gotcha found while writing tests: `get_run_logger()` needs an active run
  context and raises `MissingContextError` when a task's `.fn` is called directly (the standard
  way to unit-test Prefect tasks without the full runtime) -- fixed with a small stdlib-logger
  fallback, `_logger()`.
- `requirements-orchestration.txt`: dbt-core/dbt-postgres/prefect kept separate from
  `requirements.txt` so the deployed API image doesn't pull in either toolchain's dependency
  tree. `.github/workflows/test.yml` installs `prefect` alone (not the full dbt toolchain) since
  `tests/test_pipeline_flow.py` only imports it at module level; dbt itself is invoked as a
  subprocess inside a task body, never imported directly.
- Production schedule documented, not deployed (needs a persistent Prefect server, out of scope
  for this project's free-tier, no-server infrastructure): daily 07:00 UTC, one hour after
  `retrain-check.yml`'s existing 06:00 UTC cron. Full writeup:
  [`docs/orchestration.md`](docs/orchestration.md).

### Phase 2: dbt transformation layer (2026-09-24)
No orchestration/transformation layer existed -- `sql/analysis/*.sql` and the Python analytics
were the only consumers of raw data, each re-deriving stage durations and rework detection
independently. Added `dbt/`:

- **staging** (`stg_events`, `stg_process_cases`, `stg_suppliers`, `stg_sla_rules`): 1:1 with
  raw tables. **intermediate** (`int_stage_durations`, `int_case_rework`, `int_case_sla_scored`):
  the dbt-model versions of `bottlenecks.sql`/`rework_detection.sql`'s logic, reused as real
  models. **marts** (`fct_cases`, `dim_supplier`, `dim_category`, `mart_sla_daily`).
  `dim_category`, not `dim_business_unit` -- no such column exists in this data.
- `unique`/`not_null`/`relationships` tests plus one custom singular test
  (`assert_no_negative_stage_durations.sql`). `dbt build` run live: 30 pass, 0 errors, 2 warnings.
- **A real bug found by running `dbt build`, not by inspection:** a comment in `stg_events.sql`
  used a literal `ref()` call as a prose example, which dbt's Jinja renderer evaluated as a real
  self-referencing dependency, failing every build with "Found a cycle:
  model.operations_performance.stg_events". Fixed by describing the pattern without writing a
  literal Jinja call to the model's own name inside its own file.
- **Two real data-quality findings, surfaced by the `relationships` tests' warning counts, not
  by inspection:** `analytics.suppliers` is completely empty (0 rows; confirmed unused by any
  live code, not a production bug); `analytics.sla_rules` has only 3 categories against 10+ real
  ones in `process_cases.category`, so 2,972 of 3,000 cases fall back to the default 240h SLA
  target rather than a matched one -- a pre-existing gap in the Python pipeline too, made visible
  as a number by dbt's test rather than introduced by it. Full writeup:
  [`docs/dbt-project.md`](docs/dbt-project.md).
- `dbt docs generate` + a live `dbt docs serve` run, lineage graph captured from the real running
  page (canvas pixels POSTed to a local save server, not hand-typed base64 -- an earlier attempt
  to manually transcribe the ~30KB image data produced a corrupted file, caught by loading it
  back before committing): [`docs/dbt-lineage-graph.png`](docs/dbt-lineage-graph.png).
- `src/ml/features.py::load_evaluated_cases_from_dbt_marts()`: optional (`FEATURE_SOURCE=dbt_marts`)
  read path from `fct_cases`, feeding the same unmodified `build_features()`. Parity verified
  against live data with rows aligned by `case_id`.
- `.github/workflows/dbt.yml`: `dbt build` against a real Postgres 16 service container on every
  push, seeded via the same `scripts/setup_database.py` schema plus a small fixture.

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
