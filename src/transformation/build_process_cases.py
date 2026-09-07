import pandas as pd


def build_process_cases(events: pd.DataFrame) -> pd.DataFrame:
    events = events.sort_values(["case_id", "timestamp"])

    grouped = events.groupby("case_id")
    cases = grouped.agg(
        first_activity=("activity", "first"),
        last_activity=("activity", "last"),
        event_count=("activity", "count"),
        start_time=("timestamp", "min"),
        end_time=("timestamp", "max"),
    ).reset_index()

    cases["cycle_time_hours"] = (
        cases["end_time"] - cases["start_time"]
    ).dt.total_seconds() / 3600

    if "supplier_id" in events.columns:
        supplier = grouped["supplier_id"].first()
        cases = cases.merge(supplier, on="case_id", how="left")

    if "category" in events.columns:
        category = grouped["category"].first()
        cases = cases.merge(category, on="case_id", how="left")

    variant = grouped["activity"].apply(lambda s: " -> ".join(s))
    variant.name = "variant"
    cases = cases.merge(variant, on="case_id", how="left")

    variant_counts = cases["variant"].value_counts()
    cases["variant_frequency"] = cases["variant"].map(variant_counts)

    return cases


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from src.ingestion.load_event_log import load_event_log
    from src.cleaning.clean_events import clean_events

    load_dotenv()
    raw = load_event_log(os.environ["RAW_EVENT_LOG_PATH"])
    cleaned, _ = clean_events(raw)
    cases = build_process_cases(cleaned)
    print(cases[["case_id", "event_count", "cycle_time_hours", "variant_frequency"]].head())
    print(f"\n{cases['variant'].nunique()} distinct process variants across {len(cases)} cases")
