from pathlib import Path
import pandas as pd

RAW_COLUMN_MAP = {
    "case:concept:name": "case_id",
    "concept:name": "activity",
    "time:timestamp": "timestamp",
    "org:resource": "resource",
    "case:Purchasing Document": "purchase_order_id",
    "case:Item": "item_id",
    "case:Spend area text": "category",
    "case:Vendor": "supplier_id",
}

REQUIRED_RAW_COLUMNS = [
    "case:concept:name",
    "concept:name",
    "time:timestamp",
]


def load_event_log(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Event log not found at {path}")

    df = pd.read_csv(path, low_memory=False)

    missing = [c for c in REQUIRED_RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Event log is missing required columns: {missing}")

    present_map = {k: v for k, v in RAW_COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=present_map)

    keep = [v for v in present_map.values() if v in df.columns]
    return df[keep].copy()


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    events = load_event_log(os.environ["RAW_EVENT_LOG_PATH"])
    print(f"Loaded {len(events):,} rows, {events['case_id'].nunique():,} cases")
    print(events.head())
