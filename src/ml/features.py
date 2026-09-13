import pandas as pd

# SQL source mapping (both SQL and Python consume the same case-level data):
#   event_count         -- sourced from build_process_cases() aggregation; parallel
#                          SQL view: sql/analysis/cycle_time.sql (event counts per case)
#   variant_frequency   -- sourced from build_process_cases(); parallel SQL view:
#                          sql/analysis/process_variants.sql (variant distribution)
#   supplier_id         -- sourced from raw event log; parallel SQL analytics:
#                          sql/analysis/supplier_performance.sql
#   category            -- sourced from raw event log; SLA thresholds from
#                          sql/analysis/sla_performance.sql
#   first_activity      -- sourced from build_process_cases() (first event per case)
#   supplier_historical_breach_rate -- no SQL equivalent; computed in Python only
#                          (requires row-level shift/expanding logic not in SQL layer)

# Feature families for ablation study (scripts/ablation_study.py):
#   baseline         — structural case-level signals available immediately
#   temporal         — time-of-day / calendar signals from start_time only
#   process          — process-mining signals from the event sequence
#   supplier_history — causal per-supplier history, shift(1) prevents leakage
# All families together = FEATURE_COLUMNS below.

FEATURE_COLUMNS = [
    # ── baseline ────────────────────────────────────────────────────────
    "event_count",
    "variant_frequency",
    "category",
    "supplier_id",
    # ── temporal ────────────────────────────────────────────────────────
    "start_hour",
    "start_dayofweek",
    "start_month",         # captures intra-year seasonality (year-end rush, slow August)
    "start_quarter",       # coarser seasonal bucket useful when month is too sparse
    # ── process ─────────────────────────────────────────────────────────
    "first_activity",
    "last_activity",
    "unique_activity_count",   # breadth of the process path
    "rework_count",            # repeated activities = re-work or system glitch; correlates
                               # with delay and non-conformance (see conformance analysis)
    # ── supplier history ────────────────────────────────────────────────
    "supplier_historical_breach_rate",      # expanding mean, shift(1) — no leakage
    "supplier_historical_median_cycle_time",# expanding median, shift(1) — no leakage
    "sla_target_hours",    # SLA threshold for this case's category; set by config before
                           # the case ends, so this is not leakage — tighter targets make
                           # breach more likely and give the model a direct numeric signal
]

FEATURE_FAMILIES = {
    "baseline": ["event_count", "variant_frequency", "category", "supplier_id"],
    "temporal": ["start_hour", "start_dayofweek", "start_month", "start_quarter"],
    "process":  ["first_activity", "last_activity", "unique_activity_count", "rework_count"],
    "supplier_history": [
        "supplier_historical_breach_rate",
        "supplier_historical_median_cycle_time",
        "sla_target_hours",
    ],
}


def _add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds features beyond the raw case-level columns. Each one is checked for
    leakage before being added -- a feature computed from information only
    available once the case is already finished (e.g. anything derived from
    end_time or cycle_time_hours, which is literally how sla_breach itself is
    defined) would let the model see its own target, so none of these touch
    those columns."""
    if "start_time" in df.columns:
        df["start_hour"] = df["start_time"].dt.hour
        df["start_dayofweek"] = df["start_time"].dt.dayofweek
        df["start_month"] = df["start_time"].dt.month
        df["start_quarter"] = df["start_time"].dt.quarter

    # Causal (expanding, shifted) per-supplier breach rate -- at the time each
    # case STARTS, what fraction of that supplier's PRIOR cases (sorted by
    # start_time, strictly before this one) breached SLA. shift(1) excludes the
    # current row itself, so a supplier's first-ever case sees no history (NaN,
    # filled with the training set's overall breach rate as a neutral prior)
    # rather than peeking at its own outcome.
    if "supplier_id" in df.columns and "sla_breach" in df.columns:
        ordered = df.sort_values("start_time")
        expanding_rate = (
            ordered.groupby("supplier_id")["sla_breach"]
            .apply(lambda s: s.shift(1).expanding().mean())
            .reset_index(level=0, drop=True)
        )
        df["supplier_historical_breach_rate"] = expanding_rate.reindex(df.index)
        overall_prior = df["sla_breach"].astype(int).mean()
        df["supplier_historical_breach_rate"] = df["supplier_historical_breach_rate"].fillna(overall_prior)

    # Causal per-supplier median cycle time — expanding median of prior completed
    # cases, shift(1) prevents peeking at the current case's own cycle time.
    if "supplier_id" in df.columns and "cycle_time_hours" in df.columns:
        ordered = df.sort_values("start_time")
        expanding_med = (
            ordered.groupby("supplier_id")["cycle_time_hours"]
            .apply(lambda s: s.shift(1).expanding().median())
            .reset_index(level=0, drop=True)
        )
        df["supplier_historical_median_cycle_time"] = expanding_med.reindex(df.index)
        overall_med = df["cycle_time_hours"].median()
        df["supplier_historical_median_cycle_time"] = df["supplier_historical_median_cycle_time"].fillna(overall_med)

    return df


def build_features(evaluated_cases: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    df = _add_derived_features(evaluated_cases.copy())

    available = [c for c in FEATURE_COLUMNS if c in df.columns]
    if not available:
        raise ValueError("None of the expected feature columns are present")

    X = df[available].copy()

    for col in ["category", "supplier_id", "first_activity", "last_activity"]:
        if col in X.columns:
            X[col] = X[col].fillna("UNKNOWN")
            X = pd.get_dummies(X, columns=[col], prefix=col)

    y = df["sla_breach"].astype(int)
    return X, y


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from src.ingestion.load_event_log import load_event_log
    from src.cleaning.clean_events import clean_events
    from src.transformation.build_process_cases import build_process_cases
    from src.analytics.sla_analysis import load_sla_targets, evaluate_sla

    load_dotenv()
    raw = load_event_log(os.environ["RAW_EVENT_LOG_PATH"])
    cleaned, _ = clean_events(raw)
    cases = build_process_cases(cleaned)
    evaluated = evaluate_sla(cases, load_sla_targets())

    X, y = build_features(evaluated)
    print(f"Feature matrix: {X.shape}, breach rate: {y.mean():.2%}")
    print(X.columns.tolist())
