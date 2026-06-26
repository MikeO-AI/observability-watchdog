"""Log parsing: supports plaintext ``TIMESTAMP LEVEL ...`` lines and JSON lines.

Returns dicts with normalized keys: ts (aware datetime), level, service, message.
Unparseable lines are skipped silently so noisy real-world logs don't crash ingest.
"""
import json
import re
from datetime import datetime, timezone

LEVELS = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"}
ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}

# e.g. "2026-06-26T10:05:01Z ERROR service=checkout msg=..."
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?P<level>[A-Za-z]+)\s+"
    r"(?P<rest>.*)$"
)
_SERVICE_RE = re.compile(r"(?:service|svc|logger)=(?P<service>\S+)")


def normalize_level(level: str) -> str:
    level = level.upper()
    return "WARN" if level == "WARNING" else level


def parse_timestamp(raw: str):
    s = raw.strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_json_line(line: str):
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    ts = parse_timestamp(str(obj.get("timestamp") or obj.get("time") or obj.get("ts") or ""))
    if ts is None:
        return None
    level = normalize_level(str(obj.get("level") or obj.get("severity") or "INFO"))
    service = obj.get("service") or obj.get("logger") or obj.get("svc")
    message = str(obj.get("message") or obj.get("msg") or "")
    return {"ts": ts, "level": level, "service": service, "message": message}


def parse_line(line: str):
    line = line.rstrip("\n")
    if not line.strip():
        return None
    if line.lstrip().startswith("{"):
        return _parse_json_line(line)
    m = _LINE_RE.match(line)
    if not m:
        return None
    ts = parse_timestamp(m.group("ts"))
    if ts is None:
        return None
    rest = m.group("rest")
    svc = _SERVICE_RE.search(rest)
    return {
        "ts": ts,
        "level": normalize_level(m.group("level")),
        "service": svc.group("service") if svc else None,
        "message": rest,
    }


def parse_text(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        entry = parse_line(line)
        if entry is not None:
            out.append(entry)
    return out
