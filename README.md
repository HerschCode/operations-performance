# Procurement Process Intelligence & SLA Triage

![Tests](https://github.com/HerschCode/operations-performance/actions/workflows/test.yml/badge.svg)
![dbt](https://github.com/HerschCode/operations-performance/actions/workflows/dbt.yml/badge.svg)

**Live API:** <https://operations-performance.onrender.com/docs> (Neon Postgres, real BPI 2019 procurement
data; free tier, the first request may be slow to wake). A conversational layer over the same data lives
in [`operations-assistant`](https://operations-assistant.onrender.com).

## Headline

> **Late-stage SLA triage model: 0.83–0.89 ROC-AUC on realistic targets; early-case 0.62–0.76.**

This is a **late-stage triage score, not a creation-time predictor.** Most of the model's skill comes from
features only known late in a case (event count, full activity path). On the configured SLA targets 97% of
held-out cases breach, so the 0.986 the training script prints is inflated by a degenerate target; the
figures above come from percentile-based targets with 27–52% base rates. Details and every caveat:
[`docs/evaluation.md`](docs/evaluation.md).

| Setting | ROC-AUC | Where |
|---|---|---|
| Full-case features, realistic base rates (27–52%) | **0.83–0.89** | [`less-degenerate-target.md`](docs/less-degenerate-target.md) |
| Creation-time features only | 0.51–0.65 | [`prediction-time-availability.md`](docs/prediction-time-availability.md) |
| Prefix (first k events) RF | 0.62–0.76 | [`prefix-model-bpi2019.md`](docs/prefix-model-bpi2019.md) |
| GRU/LSTM on the first k events | 0.51–0.76 (RF kept) | [`sequence-model.md`](docs/sequence-model.md) |
| Independent log (BPI 2012), first 3 events | 0.77–0.92 | [`external-validation-bpi2012.md`](docs/external-validation-bpi2012.md) |

## What this is

An operations-analytics platform for a Procure-to-Pay process (fictional client *Northstar Manufacturing*):
event-log ingestion, SQL process mining, an SLA-breach risk model with calibrated probabilities, a FastAPI
service, and the MLOps around it (dbt, Prefect, drift monitoring, an intervention ROI ledger). The
public event log has no real interventions, business costs or SLAs, so those parts are labelled as
assumptions or simulation wherever they appear.

![Architecture](docs/architecture.svg)

## What's in it

| Area | What it does | Docs |
|---|---|---|
| **Analytical SQL** | 10 window-function queries (LAG, NTILE, RANGE frames, FIRST/LAST_VALUE), run against Neon; EXPLAIN before/after for the index change, including a result that did not improve | [`sql-window-functions.md`](docs/sql-window-functions.md) |
| **dbt** | staging → intermediate → marts, 30 passing tests, lineage graph, CI job; ML features can read `fct_cases` (`FEATURE_SOURCE=dbt_marts`, parity-checked) | [`dbt-project.md`](docs/dbt-project.md) |
| **Orchestration** | Prefect flow: ingest → DQ gate → dbt → retrain gate → train → promote only if it beats the deployed model by a margin → report | [`orchestration.md`](docs/orchestration.md) |
| **Feature drift** | Per-feature PSI against training baselines, `GET /health/drift/features`, drift as a retrain trigger, proven on simulated drift | [`feature-drift.md`](docs/feature-drift.md) |
| **Sequence model** | GRU/LSTM vs prefix RF, k∈{1,2,3,5}, ROC/PR/Brier/CPU latency, MLflow-logged. Mixed result, RF kept | [`sequence-model.md`](docs/sequence-model.md) |
| **Intervention ROI** | `interventions` ledger, `POST /interventions`, `GET /roi/summary`. Effects are **assumptions**, not measured uplift | [`uplift-method.md`](docs/uplift-method.md) |
| **Model** | Random forest (deployed), LR, GB; temporal split, isotonic calibration, SHAP explanations, ablations, bootstrap CIs | [`ml-model.md`](docs/ml-model.md) |
| **Ops** | Prometheus `/metrics`, structured logs, per-client API keys, read-only DB role, data contract and DQ checks | [`security-notes.md`](docs/security-notes.md) |

## API (selection)

| Endpoint | Purpose |
|---|---|
| `GET /orders/{case_id}/risk?explain=true` | Breach probability, risk level, SHAP top factors |
| `GET /metrics/sla`, `/metrics/cycle-time`, `/metrics/bottlenecks` | SLA, cycle-time and stage analytics |
| `GET /suppliers/performance` | Supplier scorecard |
| `GET /health/model`, `/health/drift/features` | Model age/metrics, per-feature PSI (unauthenticated) |
| `GET /observability/data-quality`, `/observability/prediction-drift` | DQ report, output-distribution drift |
| `POST /interventions`, `GET /roi/summary` | Intervention ledger (admin), simulated vs logged ROI |
| `GET /metrics` | Prometheus scrape target |

Existing routes are stable: `operations-assistant` consumes them, so new work only adds endpoints.

## Reproduce

```bash
cp .env.example .env                       # DB credentials (Neon needs DB_SSLMODE=require)
pip install -r requirements.txt
python -m scripts.setup_database           # schema, indexes, interventions table
python -m scripts.run_pipeline             # ingest → staging.events / analytics.process_cases
python -m src.ml.train                     # train + save the model (writes MLflow run)
python -m scripts.run_analysis             # API at http://localhost:8000/docs
```

Every number in this repo is regenerated by one command:

| Result | Command |
|---|---|
| Realistic-target ROC-AUC | `python -m scripts.target_sensitivity` |
| Creation-time vs late features | `python -m scripts.prediction_time_check` |
| Prefix model | `python -m scripts.prefix_model_bpi2019` |
| GRU/LSTM comparison (needs `requirements-sequence.txt`) | `python -m scripts.sequence_model_bpi2019` |
| SQL analysis | `python -m scripts.run_sql_analysis` |
| dbt build | `cd dbt && dbt build --profiles-dir .` |
| Full flow (needs `requirements-orchestration.txt`) | `python -m flows.pipeline_flow` |
| Feature baselines for an existing model | `python -m scripts.backfill_feature_baselines` |
| Simulated intervention ROI | `python -m scripts.simulate_interventions` |
| Tests | `python -m pytest` (163 pass, 18 opt-in live-DB tests skipped by default) |

## Known limits

- **Degenerate configured targets** (97% breach) and a static replay dataset: drift alerts on 9 of 10
  features because "recent" is the later period of the same sample, not a live stream.
- **ROI numbers are a simulation**; no randomized holdout exists, so there is no measured uplift.
- `analytics.suppliers` is empty and `sla_rules` covers 3 categories, so most cases use the 240 h default.
- Early-case models are weak on this data; the sequence model does not clearly beat the RF.
- Cloud migration (BigQuery/Cloud Run) is code-only and **not run**; it is deferred.

Change history: [`CHANGELOG.md`](CHANGELOG.md) · development log: [`docs/development-log.md`](docs/development-log.md) ·
feature spec: [`FEATURES.md`](FEATURES.md).
