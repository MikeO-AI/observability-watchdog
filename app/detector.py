"""Anomaly detection: error-rate spikes via a rolling-baseline z-score.

The detection logic buckets log entries into fixed time windows, then flags any
bucket whose error count sits ``ZSCORE_THRESHOLD`` standard deviations above the
mean of the trailing ``BASELINE_WINDOW`` buckets. A noise floor (``MIN_ERROR_COUNT``)
suppresses statistically-large-but-operationally-trivial blips.
"""
import math
from collections import OrderedDict
from datetime import datetime, timezone

from .parser import ERROR_LEVELS


def floor_ts(dt: datetime, bucket_seconds: int) -> datetime:
    epoch = int(dt.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % bucket_seconds), tz=timezone.utc)


def build_buckets(entries: list[dict], bucket_seconds: int) -> list[dict]:
    """Collapse entries into chronologically-ordered per-window counts."""
    buckets: "OrderedDict[datetime, dict]" = OrderedDict()
    for e in sorted(entries, key=lambda x: x["ts"]):
        key = floor_ts(e["ts"], bucket_seconds)
        b = buckets.setdefault(key, {"ts": key, "total": 0, "errors": 0})
        b["total"] += 1
        if e["level"] in ERROR_LEVELS:
            b["errors"] += 1
    return list(buckets.values())


def severity_for(zscore: float, error_count: int) -> str:
    if zscore >= 6 or error_count >= 50:
        return "critical"
    if zscore >= 4 or error_count >= 20:
        return "high"
    if zscore >= 3:
        return "medium"
    return "low"


def detect_anomalies(
    buckets: list[dict], window: int, z_threshold: float, min_errors: int
) -> list[dict]:
    anomalies: list[dict] = []
    errors = [b["errors"] for b in buckets]

    for i, bucket in enumerate(buckets):
        if i < window:
            continue  # not enough history yet to form a baseline

        baseline = errors[i - window : i]
        mean = sum(baseline) / len(baseline)
        variance = sum((x - mean) ** 2 for x in baseline) / len(baseline)
        std = math.sqrt(variance)
        current = bucket["errors"]

        # A spike out of a perfectly-flat baseline (std == 0) is treated as a
        # strong anomaly so brand-new error storms aren't missed.
        if std == 0:
            zscore = 99.0 if current > mean else 0.0
        else:
            zscore = (current - mean) / std

        if current >= min_errors and zscore >= z_threshold:
            anomalies.append(
                {
                    "bucket_ts": bucket["ts"],
                    "error_count": current,
                    "total_count": bucket["total"],
                    "baseline_mean": round(mean, 2),
                    "baseline_std": round(std, 2),
                    "zscore": round(zscore, 2),
                    "severity": severity_for(zscore, current),
                }
            )
    return anomalies
