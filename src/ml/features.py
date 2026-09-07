import pandas as pd

FEATURE_COLUMNS = [
    "event_count",
    "variant_frequency",
    "category",
    "supplier_id",
]


def build_features(evaluated_cases: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    df = evaluated_cases.copy()

    available = [c for c in FEATURE_COLUMNS if c in df.columns]
    if not available:
        raise ValueError("None of the expected feature columns are present")

    X = df[available].copy()

    for col in ["category", "supplier_id"]:
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
