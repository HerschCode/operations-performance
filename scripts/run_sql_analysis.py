"""Runs every window-function query in sql/analysis/ against the live database and prints the
first 5 rows of each -- the reproduction path docs/sql-window-functions.md points to. Read-only
(SELECT statements only); does not touch schema or data.
"""
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from scripts.setup_database import get_engine

FILES = [
    "waiting_time_lag.sql",
    "variant_ranking.sql",
    "rolling_sla_breach_rate.sql",
    "monthly_cohort_breach_trend.sql",
    "supplier_quartiles.sql",
    "slowest_stage_per_case.sql",
    "running_event_count.sql",
    "category_relative_cycle_time.sql",
    "bottlenecks.sql",
]


def main():
    load_dotenv()
    engine = get_engine()
    sql_dir = Path(__file__).resolve().parent.parent / "sql" / "analysis"

    with engine.connect() as conn:
        for name in FILES:
            sql = (sql_dir / name).read_text()
            rows = conn.execute(text(sql)).fetchall()
            print(f"\n=== {name} ({len(rows)} rows) ===")
            for r in rows[:5]:
                print("  ", tuple(r))


if __name__ == "__main__":
    main()
