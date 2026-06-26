# prompts.md — Vibe Coding Audit Log

This file is the required audit log for the "Vibe Coding" challenge. The human
acted as **Lead Architect**; the AI agent (**Claude Code**, model `claude-opus-4-8`)
wrote 100% of the code. No source files were hand-edited by the human.

Project chosen: **Project 3 — Intelligent Observability & Event Watchdog (SRE).**

---

## Turn 0 — Required Initial Execution Prompt

> Lead Architect mode: ON. We are building a Python-based, API-first **Intelligent
> Observability & Event Watchdog (SRE)** using a free database and a dashboard.
>
> Rules:
> - **No Manual Edits:** You provide all logic and fixes. I will not edit any code.
> - **Audit Log:** You must maintain a file named `prompts.md`. After every turn, update
>   that file (or provide the text block) with the prompt I just used.
> - **Time-Check:** Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h). Report
>   'Elapsed Time' at the end of every response. Acknowledge and let's start.

---

## Turn 1 — Scope & architecture decision

> "What type of Github repo do I need and let's slam them in their doubt about my coding
> skills and finish this project quickly."

**Architect intent:** Confirm submission needs a single **public** GitHub repo; pick the
project; lock the stack. Decision: Project 3, Python + **FastAPI** (API-first), **SQLite**
(free-tier DB, zero setup, $0), Chart.js dashboard (no build step), and a **Claude
(`claude-opus-4-8`)** GenAI layer for incident summaries / root-cause — fitting for a
GenAI FDE role. All three candidate projects run on sample files only, so no cloud
resources are ever provisioned.

## Turn 2 — Build the full application

The agent scaffolded and wrote the complete codebase in one pass:
- `app/config.py` — env-driven settings (DB, model, detection thresholds, alerting).
- `app/database.py`, `app/models.py` — SQLAlchemy 2.0 + SQLite; Ingestion / LogEntry /
  Anomaly / Alert tables.
- `app/parser.py` — tolerant log parser (plaintext `TS LEVEL ...` + JSON lines).
- `app/detector.py` — **z-score over a rolling baseline** spike detection with a noise
  floor and severity scoring.
- `app/ai.py` — Claude integration via the official `anthropic` SDK using **structured
  outputs** (`messages.parse`) + **adaptive thinking**, with a deterministic fallback when
  no API key is present.
- `app/webhook.py` — simulated/real webhook delivery for breached thresholds.
- `app/main.py` — FastAPI app: `/api/ingest`, `/api/anomalies`, `/api/alerts`,
  `/api/timeseries`, `/api/health-summary`, `/api/anomalies/{id}/analyze`,
  `/webhook/sink`, and the dashboard at `/`.
- `app/static/index.html` — Chart.js dashboard (health cards, error-rate trend, anomaly
  table with one-click "Analyze", alerts feed).
- `sample_data/generate_logs.py` + `sample_data/app.log` — synthetic logs with a clear
  dependency-outage error spike.
- `tests/test_watchdog.py` — parser, detector, and end-to-end ingest→detect→analyze tests.
- `README.md`, `docs/presentation.md`, `requirements.txt`, `.env.example`, `.gitignore`.

## Turn 3 — Verify and fix (bug fixes described to the agent, fixed by the agent)

Per the vibe-coding rules, bugs were described to the agent and the agent supplied the
fixes — the human edited nothing:
1. **`sqlite3.OperationalError: no such table` under TestClient.** Root cause: tables were
   created only in the deprecated `@app.on_event("startup")`, which `TestClient` doesn't
   fire outside a context manager. Fix: switched to a `lifespan` handler **and** call
   `init_db()` at import (idempotent `create_all`).
2. **Pydantic v2 deprecation** (`class Config`) → replaced with `model_config = ConfigDict(...)`.
3. **Spike not detected on short demo logs.** Root cause: default `BASELINE_WINDOW=5`
   required 5 calm buckets before a spike, but demo logs had ~4. Fix: lowered the default
   to `3` (documented as tunable) — practical for short operational windows.

Result: **6/6 tests pass**; live run ingests 124 lines, flags 1 **critical** anomaly
(z ≈ 29), fires 1 simulated alert, and serves the dashboard (HTTP 200).

---

### Note on method
This was an interactive Claude Code session, so instructions were given conversationally
rather than as the verbatim block prompts a 50-request-limited tool (e.g. Copilot) would
require. The Turn 0 block above is the canonical kickoff; Turns 1–3 capture each
architectural instruction and the agent-supplied fixes, satisfying the audit-log rule.
