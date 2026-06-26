"""Generate a synthetic application log with a clear error spike for demos/tests.

Usage:
    python sample_data/generate_logs.py > sample_data/app.log

Produces ~6 minutes of logs: a calm baseline of mostly-INFO traffic, then a
sharp burst of ERRORs in one window (a simulated dependency outage), then recovery.
"""
import random
from datetime import datetime, timedelta, timezone

random.seed(7)

SERVICES = ["checkout", "auth", "catalog", "payments", "gateway"]
INFO_MSGS = [
    'msg="request completed" status=200 path=/api/cart',
    'msg="cache hit" key=user:profile',
    'msg="healthcheck ok"',
    'msg="order placed" order_id={oid}',
]
WARN_MSGS = ['msg="slow query" duration_ms=812', 'msg="retrying upstream" attempt=2']
ERROR_MSGS = [
    'msg="connection refused" upstream=payments-db host=10.0.4.7:5432',
    'msg="timeout waiting for upstream" upstream=payments-db timeout_ms=5000',
    'msg="500 from dependency" dependency=payments-db',
    'msg="connection pool exhausted" pool=payments active=50 max=50',
]


def line(ts, level, service, msg):
    return f"{ts.strftime('%Y-%m-%dT%H:%M:%SZ')} {level} service={service} {msg}"


def emit():
    start = datetime(2026, 6, 26, 10, 0, 0, tzinfo=timezone.utc)
    out = []
    for minute in range(6):
        spike = minute == 4  # the outage window
        for _ in range(random.randint(18, 26)):
            offset = random.randint(0, 59)
            ts = start + timedelta(minutes=minute, seconds=offset)
            svc = random.choice(SERVICES)
            roll = random.random()
            if spike and roll < 0.75:
                out.append((ts, line(ts, "ERROR", "payments", random.choice(ERROR_MSGS))))
            elif roll < 0.04:
                out.append((ts, line(ts, "ERROR", svc, random.choice(ERROR_MSGS))))
            elif roll < 0.12:
                out.append((ts, line(ts, "WARN", svc, random.choice(WARN_MSGS))))
            else:
                msg = random.choice(INFO_MSGS).format(oid=random.randint(1000, 9999))
                out.append((ts, line(ts, "INFO", svc, msg)))
    out.sort(key=lambda x: x[0])
    return "\n".join(text for _, text in out)


if __name__ == "__main__":
    print(emit())
