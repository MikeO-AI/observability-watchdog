"""Tests for the watchdog: parser, detector, and an end-to-end API ingest.

A throwaway SQLite file is configured via env BEFORE importing the app, so the
suite never touches a developer's real watchdog.db.
"""
import os
import tempfile
from datetime import datetime, timezone

# Point the app at an isolated DB before any app import triggers engine creation.
_TMP_DB = os.path.join(tempfile.mkdtemp(), "test_watchdog.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ.pop("ANTHROPIC_API_KEY", None)  # force the deterministic fallback path

from fastapi.testclient import TestClient  # noqa: E402

from app.detector import build_buckets, detect_anomalies  # noqa: E402
from app.main import app  # noqa: E402
from app.parser import parse_line, parse_text  # noqa: E402

client = TestClient(app)


# --- Parser -----------------------------------------------------------------
def test_parse_plaintext_line():
    e = parse_line("2026-06-26T10:05:01Z ERROR service=payments msg=\"boom\"")
    assert e["level"] == "ERROR"
    assert e["service"] == "payments"
    assert e["ts"] == datetime(2026, 6, 26, 10, 5, 1, tzinfo=timezone.utc)


def test_parse_json_line_and_warning_normalization():
    e = parse_line('{"timestamp":"2026-06-26T10:05:01Z","level":"warning","service":"auth","msg":"slow"}')
    assert e["level"] == "WARN"  # WARNING normalized to WARN
    assert e["service"] == "auth"


def test_parse_skips_garbage():
    assert parse_line("this is not a log line") is None
    assert parse_line("") is None


# --- Detector ---------------------------------------------------------------
def _entry(minute, second, level):
    return {
        "ts": datetime(2026, 6, 26, 10, minute, second, tzinfo=timezone.utc),
        "level": level,
    }


def test_detects_error_spike():
    entries = []
    # 4 calm minutes: 1 error each. Minute 4: a 15-error spike.
    for m in range(4):
        entries.append(_entry(m, 5, "ERROR"))
        entries += [_entry(m, 10 + i, "INFO") for i in range(10)]
    entries += [_entry(4, i, "ERROR") for i in range(15)]

    buckets = build_buckets(entries, bucket_seconds=60)
    anomalies = detect_anomalies(buckets, window=3, z_threshold=3.0, min_errors=3)

    assert len(anomalies) == 1
    assert anomalies[0]["error_count"] == 15
    assert anomalies[0]["severity"] in {"high", "critical"}


def test_no_false_positive_on_flat_traffic():
    entries = [_entry(m, 5, "ERROR") for m in range(6)]  # steady 1 error/min
    buckets = build_buckets(entries, bucket_seconds=60)
    anomalies = detect_anomalies(buckets, window=3, z_threshold=3.0, min_errors=3)
    assert anomalies == []


# --- API end-to-end ---------------------------------------------------------
def _spike_log() -> str:
    lines = []
    for m in range(4):
        lines.append(f"2026-06-26T10:0{m}:05Z ERROR service=api msg=\"x\"")
        lines += [f"2026-06-26T10:0{m}:{10+i:02d}Z INFO service=api msg=\"ok\"" for i in range(10)]
    lines += [f"2026-06-26T10:04:{i:02d}Z ERROR service=payments msg=\"connection refused\"" for i in range(20)]
    return "\n".join(lines)


def test_ingest_detect_and_analyze_flow():
    files = {"file": ("app.log", _spike_log(), "text/plain")}
    r = client.post("/api/ingest", files=files)
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["anomaly_count"] >= 1
    assert summary["alerts_fired"] >= 1  # spike severity >= alert threshold

    anomalies = client.get("/api/anomalies").json()
    assert anomalies, "expected at least one anomaly"
    aid = anomalies[0]["id"]

    # Analyze uses the deterministic fallback (no API key in this test env).
    a = client.post(f"/api/anomalies/{aid}/analyze")
    assert a.status_code == 200
    body = a.json()
    assert body["source"] == "fallback"
    assert body["analysis"]["recommended_actions"]

    health = client.get("/api/health-summary").json()
    assert health["status"] in {"degraded", "critical"}
    assert health["error_events"] >= 20

    alerts = client.get("/api/alerts").json()
    assert alerts and alerts[0]["simulated"] is True  # no WEBHOOK_URL set
