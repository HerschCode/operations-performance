"""
A real, built dashboard -- closing the gap `dashboard/README.md` documented as a
Power BI/Looker build spec that was never actually built (a `.pbix` file can't live in
this repo or be inspected by anyone without that tool installed). Serves the same
`dashboard/README.md` pages (Executive Overview, Process Performance/Bottlenecks,
Supplier Performance, Conformance, SLA Risk) as one FastAPI-rendered page instead,
against the exact same `src/analytics`/`src/ml` functions the REST API and CLI reports
already use -- no separate "dashboard logic" that could drift from what `/metrics/*`
returns.

Deliberately unauthenticated (like operations-assistant's /demo/chat) -- a portfolio
visitor viewing aggregate, non-sensitive analytics shouldn't need an API key. Each
section degrades independently (a missing model or empty dataset shows that section's
own "not available" state) rather than one failure blanking the whole page.
"""
import time
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.api.db import load_events, load_cases
from src.analytics.cycle_time import cycle_time_percentiles
from src.analytics.bottlenecks import identify_bottlenecks
from src.analytics.sla_analysis import load_sla_targets, evaluate_sla, sla_summary
from src.analytics.supplier_analysis import supplier_scorecard
from src.analytics.conformance import check_conformance, conformance_report
from src.ml.predict import load_model, predict_sla_risk
from src.ml.features import build_features

router = APIRouter()


def _section(fn, *args):
    """Runs one dashboard section's data-gathering function and normalizes its
    outcome to {"available": bool, ...} -- so one section failing (no model trained
    yet, empty table, missing config) shows as that section's own empty state on the
    page instead of a 500 that blanks every other section too."""
    try:
        data = fn(*args)
        return {"available": True, **data}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


def _executive_overview(cases):
    if cases.empty:
        raise ValueError("No process cases loaded yet")
    evaluated = evaluate_sla(cases, load_sla_targets())
    summary = sla_summary(evaluated)
    total_breach = int(summary["breach_count"].sum())
    total_cases = int(summary["case_count"].sum())
    cycle = cycle_time_percentiles(cases)
    return {
        "case_count": total_cases,
        "mean_cycle_hours": round(cycle["mean_hours"], 1),
        "median_cycle_hours": round(cycle["median_hours"], 1),
        "p90_cycle_hours": round(cycle["p90_hours"], 1),
        "breach_rate_pct": round((total_breach / total_cases * 100) if total_cases else 0, 1),
    }


def _bottlenecks(events):
    if events.empty:
        raise ValueError("No events loaded yet")
    result = identify_bottlenecks(events, top_n=8)
    return {"stages": result.to_dict(orient="records")}


def _suppliers(cases):
    if "supplier_id" not in cases.columns:
        raise ValueError("No supplier_id column in this dataset")
    evaluated = evaluate_sla(cases, load_sla_targets())
    scorecard = supplier_scorecard(evaluated, min_volume=3)
    return {"suppliers": scorecard.head(8).to_dict(orient="records")}


def _conformance(events):
    if events.empty:
        raise ValueError("No events loaded yet")
    result = check_conformance(events)
    report = conformance_report(result)
    return {
        "conformance_rate_pct": report["conformance_rate_pct"],
        "total_cases": report["total_cases"],
        "conformant_cases": report["conformant_cases"],
        "deviation_breakdown": report["deviation_breakdown"],
    }


def _sla_risk(cases):
    if cases.empty:
        raise ValueError("No process cases loaded yet")
    evaluated = evaluate_sla(cases, load_sla_targets())
    X, _ = build_features(evaluated)
    bundle = load_model()  # raises FileNotFoundError if untrained -- caught by _section
    predictions = predict_sla_risk(X, bundle)
    counts = predictions["risk_level"].value_counts()
    return {
        "total_scored": len(predictions),
        "low": int(counts.get("LOW", 0)),
        "medium": int(counts.get("MEDIUM", 0)),
        "high": int(counts.get("HIGH", 0)),
    }


_CACHE_TTL_SECONDS = 120
_cache: dict = {"data": None, "computed_at": 0.0}


def _compute_dashboard_data() -> dict:
    # Each of load_cases()/load_events() is a full-table pull that, against this
    # project's actual free-tier Neon deployment, costs real tens-of-seconds -- see
    # the docstring on dashboard_data() below. Loading each table exactly ONCE and
    # sharing it across every section that needs it (three sections need cases, two
    # need events) cuts this from 5 round trips to 2, not 5 separate ones, which is
    # the difference between a slow-but-tolerable first load and a multi-minute one.
    # Loaded outside the per-section try/except: if the DB itself is unreachable,
    # every section should show that failure, not attempt 5 identical failing calls.
    try:
        cases = load_cases()
    except Exception as exc:
        cases = None
        cases_error = str(exc)
    try:
        events = load_events()
    except Exception as exc:
        events = None
        events_error = str(exc)

    def cases_section(fn):
        if cases is None:
            return {"available": False, "reason": cases_error}
        return _section(fn, cases)

    def events_section(fn):
        if events is None:
            return {"available": False, "reason": events_error}
        return _section(fn, events)

    return {
        "executive_overview": cases_section(_executive_overview),
        "bottlenecks": events_section(_bottlenecks),
        "suppliers": cases_section(_suppliers),
        "conformance": events_section(_conformance),
        "sla_risk": cases_section(_sla_risk),
    }


@router.get("/dashboard/data")
def dashboard_data():
    # A hosted free-tier Postgres (Neon, this project's actual deployment) has real,
    # non-trivial per-query latency on a full-table pull -- confirmed directly: a
    # plain `SELECT * FROM staging.events` on this project's 32K-row real BPI 2019
    # table took 60+ seconds against Neon's pooled endpoint, consistent with the
    # pipeline's own load step taking 104s for 3K rows (see operations-performance's
    # PLAN.md). Five sections each independently re-querying that same data would
    # make every dashboard page load take over a minute; a short server-side cache
    # is the honest fix here, not a workaround -- this data changes when the
    # pipeline reruns (hourly/daily at most), not per-request.
    now = time.monotonic()
    if _cache["data"] is None or (now - _cache["computed_at"]) > _CACHE_TTL_SECONDS:
        _cache["data"] = _compute_dashboard_data()
        _cache["computed_at"] = now
    return _cache["data"]


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard_page():
    return (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
