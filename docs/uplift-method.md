# Intervention ROI and uplift method (Phase 6)

> **This is a simulation.** No intervention has ever been run on this data (a public event log), so no
> effect size here was measured. Every number in `/roi/summary` is an arithmetic consequence of the
> assumptions in [`config/interventions.yaml`](../config/interventions.yaml), and the API says so in
> its `label` field and echoes the assumptions back.

## What exists
- `analytics.interventions` (`sql/schema/005_create_interventions.sql`): one row per action on a case:
  type, model risk at the time, cost, outcome once known, and `is_simulated`. One row per (case, type).
- `POST /interventions` (admin role): validates type against the policy, risk in [0, 1], cost ≥ 0,
  and that the case exists (422 / 404 / 409 on duplicates). It uses a separate write engine
  (`LEDGER_DB_USER`/`LEDGER_DB_PASSWORD`, falling back to `DB_USER`), because the API's normal
  credential is the SELECT-only `ops_api_reader` role by design.
- `GET /roi/summary`: simulated and logged rows reported **separately**, never blended.
- `python -m scripts.simulate_interventions`: policy replay — act on the top 20% of the held-out window
  (last 20% by start time, unseen in training) by model risk with `expedite_approval`; loads
  `is_simulated = TRUE` rows, idempotently.

## Arithmetic
For each treated case, the assumed relative effect *e* of its type cuts breach probability by *e*.
- Avoided breaches (by model risk) = Σ risk × e. Avoided (by observed outcomes) = Σ e over treated
  cases that did breach (only where the outcome is known).
- Net value = avoided × `breach_cost` − Σ cost.
- Break-even effect = Σ cost / (`breach_cost` × Σ risk): the uniform effect at which net value is zero.
  This is the honest headline, because it doesn't depend on a guessed effect.

## Live simulation result
120 interventions, cost 3,000, 18.0 avoided breaches by model risk (17.4 by observed outcomes), net
+4,200 (+3,960). **Break-even effect: 6.25%** — under these assumed costs and a 400 breach cost, the
action pays for itself if it prevents more than ~1 breach in 16 among treated cases.

## Why this is not uplift, and what real uplift needs
- **Effect sizes are assumed.** Uplift is the *difference in outcome caused by treatment*; it cannot be
  read from a risk model. A risk score says who is likely to breach, not who is *helped* by an action —
  high-risk cases may be unfixable, and the best targets are often mid-risk.
- **The counterfactual is missing.** A real estimate needs a randomized holdout (treat a random share of
  flagged cases, leave the rest), then compare breach rates, ideally with an uplift model (two-model or
  causal-forest) trained on that data. The ledger (`applied_at`, `breached_after`) is shaped to collect it.
- **Risk scores are the served model's probabilities** -- the isotonic-calibrated random forest
  (`bundle["model"]`, a `CalibratedClassifierCV`; the raw forest is kept separately as
  `uncalibrated_model` and is not used). The calibration layer was fit on the training split, the same rows
  the forest saw, so it can still be over-confident on new data. The configured SLA targets make ~94%
  of cases breach, so the top-20% by risk are nearly all ≈1.0 risk. Consequently "by model risk" and "by
  observed outcomes" nearly agree here, and the ranking adds little over acting on any 20% of cases. On a
  less degenerate target (see [`less-degenerate-target.md`](less-degenerate-target.md)) triage would matter more.
- Cost and breach value are placeholders; change them in the YAML and rerun to see the sensitivity.

Reproduce: `python -m scripts.setup_database && python -m scripts.simulate_interventions`, then `GET /roi/summary`.
