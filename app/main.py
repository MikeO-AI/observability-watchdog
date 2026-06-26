"""FastAPI application: API-first observability watchdog with a dashboard.

Endpoints
---------
POST /api/ingest                  ingest a log file/text -> parse, detect, alert
GET  /api/anomalies               list detected anomalies
GET  /api/alerts                  list fired (or simulated) webhook alerts
GET  /api/timeseries              error-rate timeline buckets (for charting)
GET  /api/health-summary          overall service health rollup
POST /api/anomalies/{id}/analyze  run the Claude GenAI incident analysis
POST /webhook/sink                self-contained receiver for simulated alerts
GET  /                            the dashboard UI
"""
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai
from .config import settings
from .database import get_db, init_db
from .detector import build_buckets, detect_anomalies, floor_ts
from .models import Alert, Anomaly, Ingestion, LogEntry
from .parser import ERROR_LEVELS, parse_text
from .schemas import (
    AlertOut,
    AnomalyOut,
    HealthSummary,
    IngestSummary,
    TimeseriesPoint,
)
from .webhook import deliver

STATIC_DIR = Path(__file__).parent / "static"

# Ensure tables exist as soon as the app module is imported (covers TestClient
# usage that doesn't trigger lifespan, and repeated imports — create_all is idempotent).
init_db()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Intelligent Observability & Event Watchdog",
    description="Parses logs, detects error spikes, fires simulated webhook alerts, "
    "and explains incidents with Claude.",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Ingestion --------------------------------------------------------------
def _ingest_text(db: Session, text: str, source: str) -> IngestSummary:
    total_lines = sum(1 for line in text.splitlines() if line.strip())
    entries = parse_text(text)

    ingestion = Ingestion(
        source=source,
        total_lines=total_lines,
        parsed_lines=len(entries),
        error_lines=sum(1 for e in entries if e["level"] in ERROR_LEVELS),
    )
    db.add(ingestion)
    db.flush()  # assign ingestion.id

    db.add_all(
        LogEntry(
            ingestion_id=ingestion.id,
            ts=e["ts"],
            level=e["level"],
            service=e["service"],
            message=e["message"],
        )
        for e in entries
    )

    # Detect anomalies over this ingestion's buckets.
    buckets = build_buckets(entries, settings.bucket_seconds)
    found = detect_anomalies(
        buckets,
        window=settings.baseline_window,
        z_threshold=settings.zscore_threshold,
        min_errors=settings.min_error_count,
    )

    alerts_fired = 0
    for a in found:
        anomaly = Anomaly(
            ingestion_id=ingestion.id,
            window_seconds=settings.bucket_seconds,
            **a,
        )
        db.add(anomaly)
        db.flush()

        if settings.should_alert(a["severity"]):
            payload = {
                "event": "anomaly.detected",
                "anomaly_id": anomaly.id,
                "severity": a["severity"],
                "bucket_ts": a["bucket_ts"].isoformat(),
                "error_count": a["error_count"],
                "zscore": a["zscore"],
            }
            result = deliver(settings.webhook_url, payload)
            db.add(
                Alert(
                    anomaly_id=anomaly.id,
                    webhook_url=settings.webhook_url or None,
                    status_code=result.get("status_code"),
                    ok=result.get("ok", False),
                    simulated=result.get("simulated", False),
                    payload=payload,
                )
            )
            alerts_fired += 1

    ingestion.anomaly_count = len(found)
    db.commit()

    return IngestSummary(
        ingestion_id=ingestion.id,
        total_lines=total_lines,
        parsed_lines=len(entries),
        error_lines=ingestion.error_lines,
        anomaly_count=len(found),
        alerts_fired=alerts_fired,
    )


@app.post("/api/ingest", response_model=IngestSummary)
async def ingest(file: UploadFile | None = File(default=None), db: Session = Depends(get_db)):
    """Ingest logs from an uploaded file (multipart) or a raw text body."""
    if file is not None:
        raw = (await file.read()).decode("utf-8", errors="replace")
        source = file.filename or "upload"
    else:
        raw = ""
        source = "empty"
    if not raw.strip():
        raise HTTPException(status_code=400, detail="No log content provided.")
    return _ingest_text(db, raw, source)


@app.post("/api/ingest-text", response_model=IngestSummary)
async def ingest_text(request: Request, db: Session = Depends(get_db)):
    """Ingest logs from a raw text/plain request body (convenient for curl)."""
    raw = (await request.body()).decode("utf-8", errors="replace")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Empty request body.")
    return _ingest_text(db, raw, "text-body")


# --- Reads ------------------------------------------------------------------
@app.get("/api/anomalies", response_model=list[AnomalyOut])
def list_anomalies(limit: int = 200, db: Session = Depends(get_db)):
    rows = db.execute(
        select(Anomaly).order_by(Anomaly.bucket_ts.desc()).limit(limit)
    ).scalars().all()
    return rows


@app.get("/api/alerts", response_model=list[AlertOut])
def list_alerts(limit: int = 200, db: Session = Depends(get_db)):
    rows = db.execute(
        select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    ).scalars().all()
    return rows


@app.get("/api/timeseries", response_model=list[TimeseriesPoint])
def timeseries(db: Session = Depends(get_db)):
    """Error-rate timeline across all ingested logs, bucketed for charting."""
    entries = db.execute(select(LogEntry.ts, LogEntry.level)).all()
    buckets = build_buckets(
        [{"ts": ts, "level": level} for ts, level in entries],
        settings.bucket_seconds,
    )
    return [TimeseriesPoint(ts=b["ts"], total=b["total"], errors=b["errors"]) for b in buckets]


@app.get("/api/health-summary", response_model=HealthSummary)
def health_summary(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(LogEntry.id))) or 0
    errors = (
        db.scalar(select(func.count(LogEntry.id)).where(LogEntry.level.in_(ERROR_LEVELS)))
        or 0
    )
    open_anomalies = db.scalar(select(func.count(Anomaly.id))) or 0
    alerts_fired = db.scalar(select(func.count(Alert.id))) or 0
    last_ts = db.scalar(select(func.max(LogEntry.ts)))
    error_rate = round(errors / total, 4) if total else 0.0

    crit = db.scalar(
        select(func.count(Anomaly.id)).where(Anomaly.severity == "critical")
    ) or 0
    if crit or error_rate >= 0.25:
        status = "critical"
    elif open_anomalies or error_rate >= 0.05:
        status = "degraded"
    else:
        status = "healthy"

    return HealthSummary(
        status=status,
        total_events=total,
        error_events=errors,
        error_rate=error_rate,
        open_anomalies=open_anomalies,
        alerts_fired=alerts_fired,
        last_event_ts=last_ts,
    )


# --- GenAI incident analysis ------------------------------------------------
@app.post("/api/anomalies/{anomaly_id}/analyze")
def analyze(anomaly_id: int, db: Session = Depends(get_db)):
    anomaly = db.get(Anomaly, anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found.")

    window_end = anomaly.bucket_ts + timedelta(seconds=anomaly.window_seconds)
    sample_rows = db.execute(
        select(LogEntry.message)
        .where(
            LogEntry.ingestion_id == anomaly.ingestion_id,
            LogEntry.level.in_(ERROR_LEVELS),
            LogEntry.ts >= anomaly.bucket_ts,
            LogEntry.ts < window_end,
        )
        .limit(25)
    ).scalars().all()

    payload = {
        "bucket_ts": anomaly.bucket_ts.isoformat(),
        "window_seconds": anomaly.window_seconds,
        "error_count": anomaly.error_count,
        "total_count": anomaly.total_count,
        "baseline_mean": anomaly.baseline_mean,
        "baseline_std": anomaly.baseline_std,
        "zscore": anomaly.zscore,
        "severity": anomaly.severity,
    }
    analysis, source = ai.analyze_anomaly(payload, list(sample_rows))

    anomaly.analysis = {**analysis.model_dump(), "source": source}
    anomaly.analyzed = True
    db.commit()
    return {"anomaly_id": anomaly_id, "source": source, "analysis": anomaly.analysis}


# --- Simulated webhook receiver (self-contained demo target) ----------------
@app.post("/webhook/sink")
async def webhook_sink(request: Request):
    body = await request.json()
    return {"received": True, "echo": body}


# --- Dashboard --------------------------------------------------------------
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")
