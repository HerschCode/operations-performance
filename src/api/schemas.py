from pydantic import BaseModel
from typing import Literal


class HealthResponse(BaseModel):
    status: str
    database_connected: bool


class CycleTimeResponse(BaseModel):
    mean_hours: float
    median_hours: float
    p90_hours: float
    p99_hours: float
    case_count: int


class CycleTimeSegmentRow(BaseModel):
    segment: str | None
    mean_hours: float
    median_hours: float
    p90_hours: float
    case_count: int


class BottleneckRow(BaseModel):
    stage: str
    avg_hours: float
    median_hours: float
    p90_hours: float
    case_count: int
    pct_of_total_delay: float


class SlaSummaryRow(BaseModel):
    segment: str | None = None
    case_count: int
    breach_count: int
    breach_rate_pct: float


class SupplierScoreRow(BaseModel):
    supplier_id: str
    order_count: int
    avg_cycle_time_hours: float
    cycle_time_std_hours: float | None = None
    sla_breach_rate: float | None = None
    rank_by_cycle_time: float


class FactorExplanation(BaseModel):
    feature: str
    shap_value: float
    value: float


class SlaRiskResponse(BaseModel):
    case_id: str
    breach_probability: float
    risk_level: str
    explanation: list[FactorExplanation] | None = None


class PipelineRunRow(BaseModel):
    run_id: int
    started_at: str
    finished_at: str | None = None
    status: str
    raw_row_count: int | None = None
    cleaned_row_count: int | None = None
    case_count: int | None = None
    error_message: str | None = None


class ConformanceResponse(BaseModel):
    total_cases: int
    conformant_cases: int
    conformance_rate_pct: float
    deviation_breakdown: dict[str, int]


class SlaRiskBucket(BaseModel):
    risk_level: str
    case_count: int


class SlaRiskDistributionResponse(BaseModel):
    total_cases_scored: int
    buckets: list[SlaRiskBucket]


class DataQualityCheck(BaseModel):
    name: str
    status: str  # "pass" | "warn" | "fail"
    value: str
    detail: str | None = None


class DataQualityReport(BaseModel):
    overall: str  # "pass" | "warn" | "fail"
    checked_at: str
    checks: list[DataQualityCheck]


class RiskBucketDrift(BaseModel):
    bucket: str
    baseline_pct: float
    current_pct: float
    delta_pct: float
    status: str  # "stable" | "warn" | "alert"


class PredictionDriftReport(BaseModel):
    status: str  # "stable" | "warn" | "alert" | "no_baseline"
    checked_at: str
    total_current_predictions: int
    baseline_source: str
    buckets: list[RiskBucketDrift]
    note: str | None = None


class FeatureDriftRow(BaseModel):
    feature: str
    psi: float
    status: str  # "stable" | "warn" | "alert"


class FeatureDriftReportSchema(BaseModel):
    status: str  # "stable" | "warn" | "alert" | "no_baseline"
    checked_at: str
    n_current_rows: int
    alert_features: list[str]
    features: list[FeatureDriftRow]
    thresholds: dict[str, float]
    note: str | None = None


class ErrorResponse(BaseModel):
    detail: str
