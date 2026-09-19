# Prediction-time availability: what the model can actually see, and when

Reproduce: `python -m scripts.prediction_time_check` (5-fold `TimeSeriesSplit`, 3,000 cases,
93.8% breach rate).

## The finding

Several features are aggregates over the *finished* case, so they are not knowable when a
purchase order is created:

| Feature | Why it is completion-time |
|---|---|
| `event_count` | number of events in the whole case |
| `variant_frequency` | frequency of the case's full activity sequence |
| `last_activity_*` | the case's final activity |
| `unique_activity_count`, `rework_count` | computed over the whole event sequence |

The supplier-history features (`supplier_historical_*`) use only earlier-starting cases, but
an earlier case's breach/cycle time is only known once *it* has ended, which may be after the
current case starts. They are closer to prediction-time-safe than the list above, but not
strictly so.

## Measured effect (mean ROC-AUC over 5 time-ordered folds)

| Feature set | Logistic regression | Random forest |
|---|---|---|
| All 15 families (as deployed) | 0.949 | 0.944 |
| Drop the completion-time features | 0.697 | 0.690 |
| Creation-time only (also drop supplier history) | 0.595 | 0.540 |

Per-fold values are printed by the script; the creation-time-only folds range from 0.13 to
0.93 (one fold is well below chance), so that configuration is not just weaker but unstable
across time periods.

## What this means

- The deployed model is best described as a **completion-time / late-stage risk classifier**
  (useful for triage of in-flight cases as events accumulate, and for post-hoc analysis), not
  a model that scores a case "at creation, before it closes."
- Almost all of the headline ~0.95 comes from features that encode how long or complicated
  the case already was. That correlates strongly with breaching an SLA defined on cycle time.
- The honest path to a true creation-time model is a **prefix-based** formulation: build
  features from only the first *k* events (or first *t* hours) of each case and evaluate
  performance as a function of *k*. That is not implemented; this document only measures
  the gap.
- The dominant 93.8% breach rate also means ROC-AUC is measured on a heavily imbalanced set.
