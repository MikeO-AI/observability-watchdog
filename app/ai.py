"""GenAI layer: turns a raw error spike into an incident summary + root-cause
hypothesis using Claude (claude-opus-4-8).

Design notes
------------
* Uses the official ``anthropic`` SDK with **structured outputs** (``messages.parse``)
  so Claude is constrained to the :class:`IncidentAnalysis` schema — no brittle
  string parsing of the model's prose.
* Uses **adaptive thinking** (the recommended mode on Claude 4.6+ / Opus 4.8) so
  the model decides how much to reason about each incident.
* Degrades gracefully: with no ``ANTHROPIC_API_KEY`` (or if the SDK/call fails)
  it returns a deterministic, template-based analysis so the endpoint always works.
"""
from __future__ import annotations

import os

from .config import settings
from .schemas import IncidentAnalysis

try:  # the SDK is optional at runtime; the app still serves without it
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


def is_enabled() -> bool:
    return anthropic is not None and bool(os.getenv("ANTHROPIC_API_KEY"))


def _build_prompt(anomaly: dict, sample_messages: list[str]) -> str:
    samples = "\n".join(f"  - {m}" for m in sample_messages[:15]) or "  (no sample messages captured)"
    return (
        "You are an SRE incident assistant. An automated watchdog detected an error "
        "spike in application logs. Analyze it and produce a concise incident report.\n\n"
        "Detected anomaly:\n"
        f"  window start (UTC): {anomaly['bucket_ts']}\n"
        f"  window length: {anomaly['window_seconds']}s\n"
        f"  errors in window: {anomaly['error_count']}\n"
        f"  total events in window: {anomaly['total_count']}\n"
        f"  rolling baseline mean errors: {anomaly['baseline_mean']}\n"
        f"  rolling baseline std: {anomaly['baseline_std']}\n"
        f"  z-score (std-devs above baseline): {anomaly['zscore']}\n"
        f"  watchdog severity: {anomaly['severity']}\n\n"
        "Representative error log lines from the window:\n"
        f"{samples}\n\n"
        "Infer the most likely root cause from the error messages and the spike shape. "
        "Be specific and operational; if evidence is thin, say so and lower your confidence."
    )


def _fallback_analysis(anomaly: dict, sample_messages: list[str]) -> IncidentAnalysis:
    top = sample_messages[0] if sample_messages else "no representative error captured"
    return IncidentAnalysis(
        summary=(
            f"Error spike of {anomaly['error_count']} errors in a "
            f"{anomaly['window_seconds']}s window "
            f"({anomaly['zscore']} std-devs above a baseline of "
            f"{anomaly['baseline_mean']}). Severity: {anomaly['severity']}."
        ),
        probable_root_cause=(
            f"Heuristic (no LLM): dominant error pattern — \"{top}\". "
            "Set ANTHROPIC_API_KEY to enable Claude-powered root-cause analysis."
        ),
        severity_assessment=anomaly["severity"],
        recommended_actions=[
            "Inspect the affected service's recent deploys and dependency health.",
            "Correlate the spike window with upstream/downstream latency and error rates.",
            "Check resource saturation (CPU, memory, connection pools) for the window.",
        ],
        confidence="low",
    )


def analyze_anomaly(anomaly: dict, sample_messages: list[str]) -> tuple[IncidentAnalysis, str]:
    """Return (analysis, source) where source is 'claude' or 'fallback'."""
    if not is_enabled():
        return _fallback_analysis(anomaly, sample_messages), "fallback"

    client = anthropic.Anthropic()
    try:
        response = client.messages.parse(
            model=settings.claude_model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": _build_prompt(anomaly, sample_messages)}],
            output_format=IncidentAnalysis,
        )
        parsed = response.parsed_output
        if parsed is None:  # refusal or unparseable — fall back rather than 500
            return _fallback_analysis(anomaly, sample_messages), "fallback"
        return parsed, "claude"
    except Exception:  # any SDK/network/validation error → graceful fallback
        return _fallback_analysis(anomaly, sample_messages), "fallback"
