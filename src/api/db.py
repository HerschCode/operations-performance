import os
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        # Prefers a dedicated read-only API credential (API_DB_USER/API_DB_PASSWORD --
        # should be the ops_api_reader role from sql/schema/004_create_roles.sql) over
        # the pipeline's write credential, so the API can never write to the database
        # even if a bug in this code tried to. Falls back to DB_USER/DB_PASSWORD for
        # simple local dev where roles haven't been set up yet.
        user = os.environ.get("API_DB_USER", os.environ["DB_USER"])
        password = os.environ.get("API_DB_PASSWORD", os.environ["DB_PASSWORD"])
        url = (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
        )
        _engine = create_engine(url, pool_size=5, pool_timeout=30)
    return _engine


def load_events() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql("SELECT * FROM staging.events", engine)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def load_cases() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql("SELECT * FROM analytics.process_cases", engine)
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])
    return df


def check_connection() -> bool:
    try:
        get_engine().connect().close()
        return True
    except Exception:
        return False
