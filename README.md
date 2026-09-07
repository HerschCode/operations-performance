# Operations Performance

An operations analytics and process-intelligence platform for a Procure-to-Pay (P2P) process —
built for a fictional client, **Northstar Manufacturing** — that identifies bottlenecks, SLA
failures, process deviations, and supplier performance issues, and turns them into evidence-backed
recommendations.

Pairs with [`operations-assistant`](../operations-assistant), which lets a user *investigate*
these findings conversationally, combining this project's data with company policy documents.

## Data
- **Real:** BPI Challenge 2019 procurement event log (public process-mining dataset)
- **Synthetic:** business-unit, SLA-rule, and supplier-context fields not present in the real log

Full breakdown in [`docs/data-contract.md`](docs/data-contract.md).

## Stack
Python · Pandas · SQL · PostgreSQL · scikit-learn · Power BI / Looker Studio · BigQuery · GCP

## Architecture
```
BPI 2019 event log + synthetic context
              │
        Python ETL (ingest → contract check → validate → clean → transform)
              │
          PostgreSQL  ── analytics.pipeline_runs (audit trail per run)
              │
   ┌──────────┼───────────┐
   ▼          ▼            ▼
  SQL   Process analytics  ML (SLA-risk model)
   │          │            │
   └──────────┼────────────┘
              ▼
     FastAPI analytics API (src/api/) ── consumed by operations-assistant's tools
              │
              ▼
     Dashboard + management report
              │
              ▼
    BigQuery (partitioned/clustered) + Looker Studio
    -- see cloud/README.md for the Postgres-vs-BigQuery comparison
```

## Status
See [`FEATURES.md`](FEATURES.md) for the full, tiered feature specification and definition of done.

## Running locally
```
cp .env.example .env        # fill in DB credentials
pip install -r requirements.txt
python -m scripts.setup_database
python -m scripts.run_pipeline
python -m scripts.run_analysis    # starts the API at http://localhost:8000/docs
```
Scripts are run as modules (`python -m scripts.foo`, not `python scripts/foo.py`) -- the latter
puts `scripts/` on `sys.path` instead of the repo root, which breaks every `from src...` import in
the codebase. This was actually broken in this repo until Phase 30's benchmark run caught it (see
`docs/performance-notes.md` and `PLAN.md`) -- the fix was adding `scripts/__init__.py` and
switching every documented invocation to the `-m` form, which is what's shown above.
