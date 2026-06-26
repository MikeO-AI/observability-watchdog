# 🛰️ Intelligent Observability & Event Watchdog

An **API-first, Python** SRE service that ingests application/platform logs, detects
**error-rate spikes** using statistical anomaly detection, fires **simulated webhook
alerts** when thresholds are breached, **visualizes health trends** in a dashboard, and
uses **Claude (`claude-opus-4-8`)** to turn each incident into a plain-English summary and
probable root cause.

> Built for the **2026 New Hire "Vibe Coding" Challenge — Project 3 (Site Reliability)**.
> The entire codebase was written by an AI agent (Claude Code) under human architectural
> direction — see [`prompts.md`](./prompts.md).

---

## Why this design

| Requirement | Decision |
|---|---|
| Python-based | Python 3.11+ |
| API-first | **FastAPI** with OpenAPI docs at `/docs` |
| Free-tier database | **SQLite** via SQLAlchemy — zero setup, $0, no server |
| Detect anomalies / spikes "using AI logic" | **z-score over a rolling baseline** (core statistical engine) **+ a Claude GenAI layer** for incident summaries and root-cause analysis |
| Trigger a simulated webhook alert | Webhook delivery on breach; **simulated** (recorded) when no URL is configured, real POST when one is |
| Visualize health trends | Chart.js dashboard (no build step) |
| Stay within free-tier / no cloud cost | Runs **entirely locally on sample files** — no AWS/Azure resources are ever created |

---

## Architecture

```
        log file / text
              │
              ▼
   ┌──────────────────────┐     ┌───────────────────────────────┐
   │  parser.py           │     │  detector.py                  │
   │  plaintext + JSON →  │ ──► │  bucket by time window →      │
   │  {ts, level, svc,    │     │  z-score vs rolling baseline →│
   │   message}           │     │  severity scoring             │
   └──────────────────────┘     └───────────────┬───────────────┘
              │                                  │ anomaly (severity ≥ threshold)
              ▼                                  ▼
   ┌──────────────────────┐     ┌───────────────────────────────┐
   │  SQLite (SQLAlchemy) │     │  webhook.py → simulated/real  │
   │  ingestions, logs,   │ ◄── │  alert POST                   │
   │  anomalies, alerts   │     └───────────────────────────────┘
   └──────────┬───────────┘
              │  POST /api/anomalies/{id}/analyze
              ▼
   ┌────────────────────────────────────────────┐
   │  ai.py → Claude claude-opus-4-8            │
   │  (anthropic SDK, structured outputs,      │
   │   adaptive thinking) → incident summary,  │
   │   root cause, recommended actions         │
   │  ↳ deterministic fallback if no API key   │
   └────────────────────────────────────────────┘
              │
              ▼  FastAPI  +  Chart.js dashboard at  /
```

---

## Quick start

```bash
cd observability-watchdog
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# (optional) generate fresh sample logs with an error spike
python sample_data/generate_logs.py > sample_data/app.log

# run the service
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** for the dashboard, or **http://localhost:8000/docs** for the
interactive API. In the dashboard, choose `sample_data/app.log`, click **Ingest logs**, then
**Analyze** on the detected anomaly.

### Try it from the CLI

```bash
# ingest a log file
curl -F "file=@sample_data/app.log" http://localhost:8000/api/ingest

# see detected anomalies, then analyze one with Claude (or the fallback)
curl http://localhost:8000/api/anomalies
curl -X POST http://localhost:8000/api/anomalies/1/analyze
```

### Enable the Claude GenAI layer (optional)

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY in .env, then restart uvicorn
```
Without a key the `/analyze` endpoint still works — it returns a deterministic,
template-based analysis and labels the source as `fallback`.

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/ingest` | Ingest a log file (multipart `file`) → parse, detect, alert |
| `POST` | `/api/ingest-text` | Ingest a raw `text/plain` body |
| `GET`  | `/api/anomalies` | List detected anomalies |
| `GET`  | `/api/alerts` | List fired/simulated webhook alerts |
| `GET`  | `/api/timeseries` | Error-rate timeline buckets (for charting) |
| `GET`  | `/api/health-summary` | Overall health rollup (healthy/degraded/critical) |
| `POST` | `/api/anomalies/{id}/analyze` | Claude incident analysis for one anomaly |
| `POST` | `/webhook/sink` | Self-contained receiver for simulated alerts |
| `GET`  | `/` | Dashboard UI |

---

## How detection works

1. **Bucketing** — entries are grouped into fixed time windows (`BUCKET_SECONDS`, default 60s).
2. **Rolling baseline** — for each window, the mean/std of error counts over the previous
   `BASELINE_WINDOW` windows (default 3) form the baseline.
3. **Z-score** — a window is flagged when its error count is `ZSCORE_THRESHOLD`
   (default 3.0) std-devs above baseline, **and** clears a noise floor of `MIN_ERROR_COUNT`
   (default 3) — preventing statistically-large-but-trivial blips.
4. **Severity** — derived from the z-score and absolute error count (low → critical).
5. **Alert** — anomalies at/above `ALERT_SEVERITY` (default `high`) fire a webhook.

All thresholds are environment-configurable — see [`.env.example`](./.env.example).

---

## Tests

```bash
pytest -q
```
Covers the parser (plaintext/JSON/garbage), the detector (true spike vs. flat-traffic
no-false-positive), and a full ingest → detect → alert → analyze API round-trip. **6/6 pass.**

---

## Phase 1 — Tagle.ai "Tag"

**AI Readiness Type: The Navigator (Developing) — "with an Architect edge"**
Journey stage: *Foundation Operator* (Foundation mindset · High skills).
Dimensions — Autonomy 91, Competence 66, Relatedness 63, Innovation 63, Growth Mindset 38.
_(The full Tagle assessment PDF report is submitted separately per the challenge instructions.)_

This maps directly to the challenge's framing — *"you are the architect; the AI is the
engineer"*: high autonomy + strong skills, directing AI to execute a system-level vision.

---

## Cost & decommissioning

This project provisions **no cloud resources** — it runs entirely locally against sample
files and a local SQLite file. There is nothing to decommission and **no charges can be
incurred**. (The optional Claude layer makes standard Anthropic API calls only when you
supply your own key and hit `/analyze`.)

## Project layout

```
observability-watchdog/
├── app/
│   ├── config.py        # env-driven settings
│   ├── database.py      # SQLAlchemy + SQLite
│   ├── models.py        # ORM tables
│   ├── schemas.py       # Pydantic models + Claude output contract
│   ├── parser.py        # log parsing (plaintext + JSON)
│   ├── detector.py      # rolling-baseline z-score anomaly detection
│   ├── ai.py            # Claude (claude-opus-4-8) incident analysis
│   ├── webhook.py       # simulated/real alert delivery
│   ├── main.py          # FastAPI app + endpoints
│   └── static/index.html# Chart.js dashboard
├── sample_data/         # generate_logs.py + app.log
├── tests/               # pytest suite
├── docs/presentation.md # solution deck (Markdown)
├── prompts.md           # vibe-coding audit log
├── requirements.txt
└── .env.example
```
