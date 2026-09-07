# Changelog

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
