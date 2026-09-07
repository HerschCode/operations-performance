import pandas as pd


def explain_prediction(
    feature_row: pd.Series, feature_importances: dict, top_n: int = 5
) -> list[dict]:
    """Per-prediction explanation: which features this specific case has that are
    among the model's most important, and whether that feature is 'active' for this
    case (non-zero / true). This is not SHAP -- it's a lightweight, honest approximation:
    global feature importance filtered to what's actually present in this row.
    Good enough for a fresher project; note the limitation rather than overclaiming it."""
    active_features = feature_row[feature_row != 0].index.tolist()

    ranked = sorted(
        ((f, imp) for f, imp in feature_importances.items() if f in active_features),
        key=lambda kv: kv[1],
        reverse=True,
    )

    return [
        {"feature": f, "importance": round(imp, 4), "value": feature_row[f]}
        for f, imp in ranked[:top_n]
    ]


def explain_batch(
    features: pd.DataFrame, feature_importances: dict, top_n: int = 5
) -> pd.DataFrame:
    explanations = features.apply(
        lambda row: explain_prediction(row, feature_importances, top_n), axis=1
    )
    return pd.DataFrame({"top_factors": explanations})


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from src.ingestion.load_event_log import load_event_log
    from src.cleaning.clean_events import clean_events
    from src.transformation.build_process_cases import build_process_cases
    from src.analytics.sla_analysis import load_sla_targets, evaluate_sla
    from src.ml.features import build_features
    from src.ml.predict import load_model, predict_sla_risk

    load_dotenv()
    raw = load_event_log(os.environ["RAW_EVENT_LOG_PATH"])
    cleaned, _ = clean_events(raw)
    cases = build_process_cases(cleaned)
    evaluated = evaluate_sla(cases, load_sla_targets())

    X, _ = build_features(evaluated)
    bundle = load_model()
    predictions = predict_sla_risk(X, bundle)

    if not bundle.get("feature_importances"):
        print("No feature_importances in this model bundle (only random_forest has them). "
              "Retrain to pick up a random_forest model if you need explanations.")
    else:
        explanations = explain_batch(X, bundle["feature_importances"])
        output = pd.concat(
            [evaluated[["case_id"]].reset_index(drop=True), predictions, explanations], axis=1
        )
        print(output.sort_values("breach_probability", ascending=False).head(5).to_string(index=False))
