from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse
import pandas as pd

from src.api.db import load_events, load_cases, check_connection, get_engine
from src.api.auth import require_api_key
from src.api.schemas import (
    HealthResponse,
    CycleTimeResponse,
    BottleneckRow,
    SlaSummaryRow,
    SupplierScoreRow,
    SlaRiskResponse,
    FactorExplanation,
    PipelineRunRow,
    ConformanceResponse,
    SlaRiskDistributionResponse,
    SlaRiskBucket,
)
from src.analytics.cycle_time import cycle_time_percentiles, stage_summary
from src.analytics.bottlenecks import identify_bottlenecks
from src.analytics.sla_analysis import load_sla_targets, evaluate_sla, sla_summary
from src.analytics.supplier_analysis import supplier_scorecard
from src.analytics.conformance import check_conformance, conformance_report
from src.ml.predict import load_model, predict_sla_risk
from src.ml.features import build_features
from src.ml.explain_shap import explain_prediction_shap
from src.reports.generate_management_report import build_management_report, render_markdown

router = APIRouter()

# /health is intentionally on an unauthenticated router -- see src/api/auth.py's
# docstring for why (load balancer / orchestrator liveness probes conventionally
# don't carry a credential). Every other route lives on `router`, which
# src/api/main.py includes WITH the require_api_key dependency applied.
health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", database_connected=check_connection())


@router.get("/metrics/cycle-time", response_model=CycleTimeResponse)
def cycle_time():
    cases = load_cases()
    if cases.empty:
        raise HTTPException(status_code=404, detail="No process cases loaded yet -- run the pipeline first")
    return cycle_time_percentiles(cases)


@router.get("/metrics/bottlenecks", response_model=list[BottleneckRow])
def bottlenecks(top_n: int = Query(default=10, ge=1, le=50)):
    events = load_events()
    if events.empty:
        raise HTTPException(status_code=404, detail="No events loaded yet -- run the pipeline first")
    result = identify_bottlenecks(events, top_n=top_n)
    return result.to_dict(orient="records")


@router.get("/metrics/sla", response_model=list[SlaSummaryRow])
def sla_metrics(segment: str | None = Query(default=None, description="e.g. 'category'")):
    cases = load_cases()
    if cases.empty:
        raise HTTPException(status_code=404, detail="No process cases loaded yet -- run the pipeline first")

    evaluated = evaluate_sla(cases, load_sla_targets())
    summary = sla_summary(evaluated, segment_col=segment)

    segment_col = segment if segment and segment in summary.columns else "_all"
    rows = []
    for _, row in summary.iterrows():
        rows.append(SlaSummaryRow(
            segment=str(row[segment_col]) if segment_col in row else None,
            case_count=int(row["case_count"]),
            breach_count=int(row["breach_count"]),
            breach_rate_pct=float(row["breach_rate_pct"]),
        ))
    return rows


@router.get("/suppliers/performance", response_model=list[SupplierScoreRow])
def supplier_performance(min_volume: int = Query(default=5, ge=1)):
    cases = load_cases()
    if "supplier_id" not in cases.columns:
        raise HTTPException(status_code=404, detail="This dataset export has no supplier_id column")

    evaluated = evaluate_sla(cases, load_sla_targets())
    scorecard = supplier_scorecard(evaluated, min_volume=min_volume)
    return scorecard.to_dict(orient="records")


@router.get("/orders/{case_id}/risk", response_model=SlaRiskResponse)
def order_risk(case_id: str, explain: bool = Query(default=False, description="Include SHAP top-5 feature contributions in the response")):
    cases = load_cases()
    match = cases[cases["case_id"] == case_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"No case found with case_id '{case_id}'")

    sla_targets = load_sla_targets()
    evaluated = evaluate_sla(match, sla_targets)
    X, _ = build_features(evaluated)

    try:
        bundle = load_model()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="No trained SLA-risk model available -- run src/ml/train.py first",
        )

    prediction = predict_sla_risk(X, bundle)

    explanation = None
    if explain:
        # Use all cases as SHAP background (already loaded); align to the same
        # column set the model was trained on so the explainer sees the right shape.
        all_evaluated = evaluate_sla(cases, sla_targets)
        X_all, _ = build_features(all_evaluated)
        cols = bundle["columns"]
        X_all_aligned = X_all.reindex(columns=cols, fill_value=0)
        X_case_aligned = X.reindex(columns=cols, fill_value=0)
        raw = explain_prediction_shap(bundle["model"], X_all_aligned, X_case_aligned, top_n=5)
        explanation = [FactorExplanation(**f) for f in raw]

    return SlaRiskResponse(
        case_id=case_id,
        breach_probability=float(prediction.iloc[0]["breach_probability"]),
        risk_level=str(prediction.iloc[0]["risk_level"]),
        explanation=explanation,
    )


@router.get("/reports/management", response_class=PlainTextResponse)
def management_report():
    """Returns the current Finding -> Evidence -> Impact -> Recommendation report as
    markdown. This is what a scheduled job (or operations-assistant) would call to get
    the same report a human would generate by running generate_management_report.py
    directly -- one code path, two consumers."""
    events = load_events()
    cases = load_cases()
    if events.empty or cases.empty:
        raise HTTPException(status_code=404, detail="No data loaded yet -- run the pipeline first")

    report = build_management_report(events, cases)
    return render_markdown(report)


@router.get("/observability/pipeline-runs", response_model=list[PipelineRunRow])
def pipeline_runs(limit: int = Query(default=20, ge=1, le=200)):
    """Recent pipeline run history from the Phase 5 audit table -- surfaces run
    duration/success/failure without needing direct DB access. This is the
    observability layer's window into 'is the pipeline healthy', same idea as
    the request-logging middleware is for the API itself."""
    engine = get_engine()
    query = """
        SELECT run_id, started_at, finished_at, status,
               raw_row_count, cleaned_row_count, case_count, error_message
        FROM analytics.pipeline_runs
        ORDER BY started_at DESC
        LIMIT %(limit)s
    """
    df = pd.read_sql(query, engine, params={"limit": limit})
    df["started_at"] = df["started_at"].astype(str)
    df["finished_at"] = df["finished_at"].astype(str).replace("NaT", None)
    return df.to_dict(orient="records")


@router.get("/metrics/conformance", response_model=ConformanceResponse)
def conformance():
    """Wraps src/analytics/conformance.py's check against config/process.yaml's
    expected sequence. Unlocks dashboard page 5 (dashboard/README.md) and
    operations-assistant's src/tools/process.py, both of which were documented as
    waiting on this endpoint existing."""
    events = load_events()
    if events.empty:
        raise HTTPException(status_code=404, detail="No events loaded yet -- run the pipeline first")

    try:
        result = check_conformance(events)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="config/process.yaml not found -- conformance checking is not configured")

    report = conformance_report(result)
    return ConformanceResponse(
        total_cases=report["total_cases"],
        conformant_cases=report["conformant_cases"],
        conformance_rate_pct=report["conformance_rate_pct"],
        deviation_breakdown=report["deviation_breakdown"],
    )


@router.get("/metrics/sla-risk-distribution", response_model=SlaRiskDistributionResponse)
def sla_risk_distribution():
    """Batch SLA-risk prediction across every case, bucketed by risk level -- unlocks
    dashboard page 6, which per-case /orders/{id}/risk can't reasonably serve (that
    endpoint is documented as single-case-at-a-time; looping it per case for a
    dashboard view was explicitly flagged as the wrong approach when the dashboard
    spec was written). predict_sla_risk already accepts a full DataFrame natively --
    this endpoint doesn't loop, it scores every case in one batch call."""
    cases = load_cases()
    if cases.empty:
        raise HTTPException(status_code=404, detail="No process cases loaded yet -- run the pipeline first")

    evaluated = evaluate_sla(cases, load_sla_targets())
    X, _ = build_features(evaluated)

    try:
        bundle = load_model()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="No trained SLA-risk model available -- run src/ml/train.py first")

    predictions = predict_sla_risk(X, bundle)
    counts = predictions["risk_level"].value_counts()

    buckets = [
        SlaRiskBucket(risk_level=level, case_count=int(counts.get(level, 0)))
        for level in ["LOW", "MEDIUM", "HIGH"]
    ]
    return SlaRiskDistributionResponse(total_cases_scored=len(predictions), buckets=buckets)
