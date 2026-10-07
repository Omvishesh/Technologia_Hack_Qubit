"""
Agent 1 — Log Analysis Agent

Takes incident info, raw logs, and metrics, then produces a structured
LogSummary with error signals and context for hypothesis generation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..llm_client import call_llm_json
from ..models import Incident, LogSummary

logger = logging.getLogger("incident-response.agents.log_analyzer")

SYSTEM_PROMPT = """\
You are a senior Site Reliability Engineer specializing in incident log analysis.

Your task: Analyze the provided application logs and metrics from a Student Query API backend
and produce a structured summary for the incident response team.

Focus on:
1. Identifying the dominant error pattern
2. Extracting key error signals (error messages, status codes, pool stats)
3. Noting any timing/frequency patterns
4. Summarizing the overall health state

Output ONLY valid JSON with this exact schema:
{
    "summary": "A 2-3 sentence human-readable summary of what the logs show",
    "error_signals": ["signal 1", "signal 2", ...],
    "error_count": <number of error-level entries>,
    "avg_latency_ms": <average latency if available, null otherwise>,
    "dominant_error": "The most common error message or pattern",
    "time_range": "Approximate time range of the logs (e.g. '14:10 - 14:15 UTC')"
}
"""


async def analyze_logs(incident: Incident) -> LogSummary:
    """
    Analyze the raw logs attached to an incident and produce a LogSummary.

    Args:
        incident: The Incident with raw_logs and metrics populated.

    Returns:
        A LogSummary with structured analysis results.
    """
    # Build the user prompt with all available context
    user_prompt_parts = []

    user_prompt_parts.append(f"INCIDENT ID: {incident.id}")
    user_prompt_parts.append(f"ERROR CODE: {incident.error_code or 'Unknown'}")
    user_prompt_parts.append(f"ERROR MESSAGE: {incident.error_message or 'Unknown'}")
    user_prompt_parts.append("")

    # Include raw logs (truncate if too many)
    logs_to_analyze = incident.raw_logs[:50]  # Max 50 entries for context window
    user_prompt_parts.append(f"APPLICATION LOGS ({len(logs_to_analyze)} entries):")
    user_prompt_parts.append(json.dumps(logs_to_analyze, indent=2, default=str))
    user_prompt_parts.append("")

    # Include metrics if available
    if incident.metrics:
        user_prompt_parts.append("CURRENT METRICS:")
        user_prompt_parts.append(incident.metrics.model_dump_json(indent=2))

    user_prompt = "\n".join(user_prompt_parts)

    logger.info("Analyzing %d log entries for incident %s", len(logs_to_analyze), incident.id)

    try:
        result = await call_llm_json(SYSTEM_PROMPT, user_prompt)

        log_summary = LogSummary(
            summary=result.get("summary", "Unable to generate summary"),
            error_signals=result.get("error_signals", []),
            error_count=result.get("error_count", 0),
            avg_latency_ms=result.get("avg_latency_ms"),
            dominant_error=result.get("dominant_error"),
            time_range=result.get("time_range"),
            raw_log_count=len(logs_to_analyze),
        )

        logger.info(
            "Log analysis complete: %d error signals found, dominant: %s",
            len(log_summary.error_signals),
            log_summary.dominant_error,
        )

        return log_summary

    except Exception as exc:
        logger.error("Log analysis failed: %s", exc, exc_info=True)
        # Return a minimal summary on failure
        return LogSummary(
            summary=f"Log analysis failed: {exc}. "
                    f"Incident error: {incident.error_message or 'Unknown'}",
            error_signals=[incident.error_message or "Unknown error"],
            error_count=len([l for l in incident.raw_logs if l.get("status", 200) >= 500]),
            raw_log_count=len(incident.raw_logs),
        )

