# Model Card — SLA Breach Risk

## Objective
Binary classification: will this case's cycle time exceed its SLA target
(`config/sla.yaml`)? Trained and evaluated in `src/ml/train.py`.

## Training data
BPI Challenge 2019 procurement cases, transformed via `build_process_cases.py` and labeled via
`sla_analysis.evaluate_sla`. Split is **time-based, not random** (`train.py:time_based_split`):
the earliest ~80% of cases by start time are training, the most recent ~20% are test. A random
split would leak future information (e.g. a supplier's later performance trend) into training for
a temporal process like this -- that would inflate reported metrics beyond what you'd actually see
predicting forward in production.

## Features
`event_count`, `variant_frequency`, `category` (one-hot), `supplier_id` (one-hot) --
see `src/ml/features.py`. This is a deliberately minimal starting feature set; the honest next
step (not yet done) is adding supplier historical breach rate, order value, and elapsed-time-so-far
as features once `supplier_analysis.py` and richer case fields are wired in.

## Models
Three, compared on the same time-based split:
- Baseline: Logistic Regression (`class_weight="balanced"` to account for breach being the
  minority class)
- Random Forest (200 trees, max_depth=8, same class balancing)
- Gradient Boosting (150 estimators, max_depth=3, learning_rate=0.1) -- a genuinely different
  algorithm family (sequential error-correcting ensemble, vs. a single linear model, vs. a bagged
  ensemble of independent trees), worth comparing rather than assuming Random Forest is
  automatically the right choice just because it was the first non-baseline model tried.
  `GradientBoostingClassifier` doesn't support `class_weight` directly the way the other two do --
  `sample_weight` is computed manually in `train.py` for the equivalent balancing effect.

The better model by ROC-AUC on the time-based test split is saved to
`models/sla_risk_model.joblib` -- so a genuine three-way comparison determines which model ships,
not a default assumption.

## Cross-validation
`train.py:cross_validate_time_series` -- **`TimeSeriesSplit`, not standard `KFold`.** Standard
k-fold would reintroduce exactly the temporal leakage `time_based_split` exists to avoid for the
single train/test split (a fold's "training" data could easily include cases chronologically
after some of its "test" data). `TimeSeriesSplit` instead builds expanding-window folds: every
fold's test set is chronologically after everything in its training set, always. Verified directly
by a test (`test_cross_validate_time_series_folds_are_chronologically_ordered`), not just trusted
because the right sklearn class name is used.

Reports per-fold ROC-AUC plus mean/std across folds -- the std matters as much as the mean. A
model that scores well on one time window but swings wildly across others is a real stability risk
a single train/test split's one number can't reveal.

## Evaluation
Precision, recall, F1, ROC-AUC, confusion matrix -- all computed in `train.py:_evaluate`.

**Precision/recall trade-off, explicitly:** a false negative (predicted low-risk, actually
breaches) means an at-risk order gets no intervention and a client SLA gets missed. A false
positive (predicted high-risk, doesn't breach) means an analyst spends a few minutes reviewing an
order that was fine. Those costs aren't symmetric -- we'd rather over-flag than under-flag, which
is why `class_weight="balanced"` is used rather than optimizing for raw accuracy.

## Explainability
`src/ml/explain.py` reports, per prediction, which of the model's globally important features are
actually present/active for that specific case. This is **not SHAP** -- it's a lightweight
approximation (global importance filtered to the row's active features), and it's described that
way rather than oversold. SHAP is a legitimate Tier 3 upgrade if it's worth the added dependency.

## Known limitations (updated -- several of these were closed after this doc was first written; left dated rather than silently correct with no trace)
- ~~Feature set is minimal~~ **Closed.** 15 features across process, temporal, and
  causal supplier-history families (`src/ml/features.py`) -- see README's ablation study.
- ~~No monitoring for feature or label drift once trained~~ **Closed.**
  `GET /observability/prediction-drift` compares live prediction distributions against a
  training-time baseline; `GET /metrics` (Prometheus) tracks prediction volume by risk_level
  in real time. Retraining itself is still manually triggered, not automated on a drift signal.
- ~~Explainability is global-importance-based, not a true per-prediction attribution method~~
  **Closed.** Real SHAP (`src/ml/explain_shap.py`, `shap.Explainer`) is wired into
  `GET /orders/{case_id}/risk?explain=true` -- genuine per-prediction attribution, not a proxy.
- **Still open:** no fairness/bias review across supplier or category segments has been done.
- **Still open:** the single-split "which model wins" comparison this doc's model-selection
  section describes doesn't hold up under a proper paired significance test across CV folds --
  see [`docs/statistical-significance.md`](statistical-significance.md). Random forest and
  logistic regression are statistically indistinguishable; RF is kept for operational reasons
  (no scaling needed, no convergence warnings at 541 one-hot columns), not a proven accuracy edge.

## When to retrain
No automated trigger yet (Tier 3: revisit once Phase 10 observability is in place). Manually,
retrain when: the process/schema changes materially (new `config/process.yaml`), a new SLA
category is added to `config/sla.yaml`, or the test-period metrics on a fresh pull noticeably
diverge from what's reported here.
