"""Simulated webhook delivery for breached anomaly thresholds.

If ``WEBHOOK_URL`` is configured the payload is POSTed for real; otherwise the
delivery is *simulated* (recorded as an alert, not sent) so the system is fully
self-contained and free to run.
"""
import httpx


def deliver(webhook_url: str, payload: dict, timeout: float = 5.0) -> dict:
    if not webhook_url:
        return {"ok": True, "status_code": None, "simulated": True}
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=timeout)
        return {
            "ok": 200 <= resp.status_code < 300,
            "status_code": resp.status_code,
            "simulated": False,
        }
    except Exception as exc:  # network failures must not break ingestion
        return {"ok": False, "status_code": None, "simulated": False, "error": str(exc)}
