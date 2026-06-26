"""Pydantic schemas for API responses and the Claude structured-output contract."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# --- Claude structured-output contract -------------------------------------
class IncidentAnalysis(BaseModel):
    """Shape the GenAI layer is constrained to return (via structured outputs)."""

    summary: str
    probable_root_cause: str
    severity_assessment: str
    recommended_actions: List[str]
    confidence: str


# --- API response models ----------------------------------------------------
class IngestSummary(BaseModel):
    ingestion_id: int
    total_lines: int
    parsed_lines: int
    error_lines: int
    anomaly_count: int
    alerts_fired: int


class AnomalyOut(BaseModel):
    id: int
    ingestion_id: int
    bucket_ts: datetime
    window_seconds: int
    error_count: int
    total_count: int
    baseline_mean: float
    baseline_std: float
    zscore: float
    severity: str
    analyzed: bool
    analysis: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class AlertOut(BaseModel):
    id: int
    anomaly_id: int
    webhook_url: Optional[str] = None
    status_code: Optional[int] = None
    ok: bool
    simulated: bool
    payload: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimeseriesPoint(BaseModel):
    ts: datetime
    total: int
    errors: int


class HealthSummary(BaseModel):
    status: str            # healthy | degraded | critical
    total_events: int
    error_events: int
    error_rate: float
    open_anomalies: int
    alerts_fired: int
    last_event_ts: Optional[datetime] = None
