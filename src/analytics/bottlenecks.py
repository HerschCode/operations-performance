import pandas as pd
from src.analytics.cycle_time import stage_summary


def identify_bottlenecks(events: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    summary = stage_summary(events)
    total_hours = summary["avg_hours"].sum()
    summary["pct_of_total_delay"] = (summary["avg_hours"] / total_hours) * 100
    return summary.head(top_n).reset_index(drop=True)


def bottlenecks_by_segment(
    events: pd.DataFrame, cases: pd.DataFrame, segment_col: str, top_n: int = 5
) -> pd.DataFrame:
    if segment_col not in cases.columns:
        raise ValueError(f"'{segment_col}' not found in cases dataframe")

    merged = events.merge(cases[["case_id", segment_col]], on="case_id", how="left")
    results = []
    for segment_value, group in merged.groupby(segment_col):
        top = identify_bottlenecks(group, top_n=top_n)
        top[segment_col] = segment_value
        results.append(top)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from src.ingestion.load_event_log import load_event_log
    from src.cleaning.clean_events import clean_events
    from src.transformation.build_process_cases import build_process_cases

    load_dotenv()
    raw = load_event_log(os.environ["RAW_EVENT_LOG_PATH"])
    cleaned, _ = clean_events(raw)
    cases = build_process_cases(cleaned)

    print("Top bottleneck stages overall:")
    print(identify_bottlenecks(cleaned).to_string(index=False))

    if "category" in cases.columns:
        print("\nBottlenecks by category:")
        print(bottlenecks_by_segment(cleaned, cases, "category").to_string(index=False))
