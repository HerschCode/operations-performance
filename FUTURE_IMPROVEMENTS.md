# Future Improvements (Post-v1.0 Backlog)

## Done since v1.0 (moved out of this list)
`sql/analysis/*.sql` is now filled in with real SQL. `GET /metrics/conformance` and
`GET /metrics/sla-risk-distribution` are now built, unlocking both dashboard pages 5-6 and
`operations-assistant`'s `process.py` tools. Dead stub files (never-built transformation/cleaning
modules, a superseded scenario-analysis placeholder) were removed rather than left empty in a
frozen repo. API-key authentication is now real (`src/api/auth.py`). `check_conformance` is now
fully vectorized (~4x speedup, after an honestly-documented first attempt that didn't actually
help) -- see `PLAN.md` and `docs/performance-notes.md`. `scenario_analysis.py` is now real
(stage-duration what-if impact estimation, hand-verified against the golden dataset). ML model
comparison now includes Gradient Boosting plus proper time-series cross-validation
(`TimeSeriesSplit`, not standard k-fold). An automated retraining trigger now exists
(`src/ml/retrain_trigger.py`) -- time- and volume-based, real decision logic ready for a real
scheduler to call. CI now runs a `pip-audit` dependency scan.

## Still open
- SHAP-based explainability (replacing `src/ml/explain.py`'s lightweight approximation)
- An actually-built Power BI / Looker Studio dashboard (currently a documented build spec only)
- Per-client API keys, key rotation, and scopes/roles (single shared API key exists now -- see `src/api/auth.py`)
- Hyperparameter tuning (grid/random search) and MLflow experiment tracking -- 3-model comparison
  with fixed hyperparameters and time-series CV now exists (`src/ml/train.py`), tuning doesn't yet
- Wire `src/ml/retrain_trigger.py`'s decision logic to an actual scheduler (cron, Cloud Scheduler,
  a GitHub Actions cron trigger) -- the logic itself is built and tested; nothing calls it on a
  schedule yet, since that needs real infrastructure this project doesn't run
