# Intelligent Observability & Event Watchdog
### 2026 New Hire "Vibe Coding" Challenge — Project 3 (Site Reliability)
*Architect: Mike · Engineer: Claude Code (`claude-opus-4-8`)*

---

## Slide 1 — The problem

Production systems emit a constant stream of logs. Buried in the noise are **error
spikes** that signal an incident — a failing dependency, an exhausted pool, a bad deploy.

SRE teams need to:
- detect those spikes **automatically**, before users do,
- get **alerted** the moment a threshold is breached,
- **understand** the incident fast — what broke and why,
- **see** health trends at a glance.

---

## Slide 2 — The solution

An **API-first watchdog** that closes that loop:

**Ingest → Detect → Alert → Explain → Visualize**

- **Python + FastAPI** — clean REST API (`/docs` out of the box)
- **SQLite** — free-tier, zero-setup persistence
- **Statistical engine** — rolling-baseline z-score spike detection
- **GenAI layer** — Claude turns each spike into an incident report
- **Dashboard** — Chart.js health trends, anomalies, and alerts

Runs **100% locally, $0** — no cloud resources, nothing to decommission.

---

## Slide 3 — How detection works

```
errors per 60s window:   1   0   1   0   1   ███ 14 ███   2   1
                         └──── baseline ────┘   ▲
                          mean≈0.6, std≈0.5     │  z ≈ 29  → CRITICAL
                                                └─ flagged
```

1. **Bucket** log entries into time windows
2. **Baseline** = mean/std of error counts over the trailing N windows
3. **Flag** when a window is ≥ 3σ above baseline *and* clears a noise floor
4. **Score** severity from z-score + absolute count
5. **Alert** when severity ≥ threshold → webhook fires

Every threshold is environment-tunable.

---

## Slide 4 — The GenAI layer (why this is a *GenAI* FDE project)

`POST /api/anomalies/{id}/analyze` → **Claude `claude-opus-4-8`**

- Official **Anthropic SDK** with **structured outputs** — Claude is constrained to a
  typed `IncidentAnalysis` schema (summary · root cause · severity · recommended actions
  · confidence). No brittle prose parsing.
- **Adaptive thinking** — the model reasons proportionally to incident complexity.
- **Graceful degradation** — no API key? A deterministic heuristic analysis is returned
  and labeled `fallback`, so the product never breaks.

> Statistical detection finds *that* something is wrong; the LLM explains *what* and
> *why*, and proposes next actions.

---

## Slide 5 — Live result (sample data)

Ingested **124 log lines** with a simulated `payments-db` outage:

| Metric | Value |
|---|---|
| Parsed lines | 124 |
| Error lines | 16 |
| Anomalies detected | **1** |
| Severity | **CRITICAL** (z ≈ 29) |
| Alerts fired | **1** (simulated webhook) |
| Health status | **CRITICAL** |

Claude's root cause (representative): *"timeout / connection-pool exhaustion against
`payments-db` — a downstream dependency outage; scale or fail over the connection pool and
check DB health."*

---

## Slide 6 — Architecture at a glance

```
log → parser → detector (z-score) → SQLite
                     │
                     ├─► webhook alert (simulated/real)
                     └─► Claude incident analysis (on demand)
                              │
                     FastAPI + Chart.js dashboard
```

- `parser.py` · `detector.py` · `ai.py` · `webhook.py` · `main.py`
- Fully tested: parser, detector, and end-to-end API flow — **6/6 green**

---

## Slide 7 — Engineering rigor & the "vibe coding" method

- **100% AI-written** under human architectural direction (see `prompts.md`)
- **No manual code edits** — bugs were *described*, fixes *generated* (e.g. test-time DB
  init via `lifespan`, baseline-window tuning)
- Tests, sample-data generator, `.env.example`, graceful fallbacks, typed schemas
- Tag fit: **The Navigator · Architect edge** — high autonomy directing AI to ship a
  system-level vision

---

## Slide 8 — What's next

- Streaming/continuous ingest (tail a live log source) + scheduled re-evaluation
- EWMA / seasonal baselines for traffic with daily cycles
- Per-service anomaly attribution and alert deduplication
- Real webhook targets (PagerDuty/Slack) + alert acknowledgement workflow

**Thank you.** → `README.md` to run it in 60 seconds.
