"""
Agent 2 — Hypothesis Generator

Takes the log summary and generates exactly 3 ranked root-cause hypotheses,
each with a confidence score and the verification tool to call.
"""

from __future__ import annotations

import json
import logging

from ..llm_client import call_llm_json
from ..models import Incident, Hypothesis
from ..error_catalogue import get_catalogue_summary

logger = logging.getLogger("incident-response.agents.hypothesis_generator")

SYSTEM_PROMPT = """\
You are an expert incident response analyst for a Student Query API system.

Your task: Based on the log analysis summary and error signals, generate exactly 3 ranked
root-cause hypotheses. Each hypothesis must map to a verification tool that can confirm or deny it.

Available verification tools:
- check_db_connections: Checks PostgreSQL connection pool status (active, max, waiting, exhausted)
- check_db_health: Checks database reachability, ping latency, and query ability
- check_backend_load: Checks CPU%, memory, and active HTTP request count

Known error catalogue:
{catalogue}

Output ONLY valid JSON — an array of exactly 3 objects with this schema:
[
    {{
        "rank": 1,
        "title": "Short descriptive title of the hypothesis",
        "description": "Detailed explanation of why this could be the root cause",
        "confidence": 0.75,
        "verification_tool": "check_db_connections",
        "expected_if_true": "What the tool result should show if this hypothesis is correct"
    }},
    ...
]

Rules:
1. Rank by confidence (highest first). Confidences must sum to approximately 1.0.
2. Each hypothesis MUST use one of the three available verification tools.
3. Be specific about the expected_if_true — reference concrete metric values.
4. Base your analysis on the actual error signals provided, not generic guesses.
"""


async def generate_hypotheses(incident: Incident) -> list[Hypothesis]:
    """
    Generate 3 ranked root-cause hypotheses based on the incident's log summary.

    Args:
        incident: The Incident with log_summary populated.

    Returns:
        List of exactly 3 Hypothesis objects, ranked by confidence.
    """
    catalogue = get_catalogue_summary()
    system_prompt = SYSTEM_PROMPT.format(catalogue=catalogue)

    # Build user prompt
    user_prompt_parts = [
        f"INCIDENT ID: {incident.id}",
        f"ERROR CODE: {incident.error_code or 'Unknown'}",
        f"ERROR MESSAGE: {incident.error_message or 'Unknown'}",
        "",
    ]

    if incident.log_summary:
        user_prompt_parts.extend([
            "LOG ANALYSIS SUMMARY:",
            f"Summary: {incident.log_summary.summary}",
            f"Error Signals: {json.dumps(incident.log_summary.error_signals)}",
            f"Error Count: {incident.log_summary.error_count}",
            f"Dominant Error: {incident.log_summary.dominant_error or 'N/A'}",
            f"Avg Latency: {incident.log_summary.avg_latency_ms or 'N/A'} ms",
            "",
        ])

    if incident.metrics:
        user_prompt_parts.extend([
            "CURRENT METRICS:",
            incident.metrics.model_dump_json(indent=2),
        ])

    user_prompt = "\n".join(user_prompt_parts)

    logger.info("Generating hypotheses for incident %s", incident.id)

    try:
        result = await call_llm_json(system_prompt, user_prompt)

        hypotheses = []
        for item in result[:3]:  # Ensure max 3
            hypotheses.append(Hypothesis(
                rank=item["rank"],
                title=item["title"],
                description=item["description"],
                confidence=float(item["confidence"]),
                verification_tool=item["verification_tool"],
                expected_if_true=item["expected_if_true"],
            ))

        # Sort by confidence descending
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)

        # Re-assign ranks after sorting
        for i, h in enumerate(hypotheses, 1):
            h.rank = i

        logger.info(
            "Generated %d hypotheses. Top: %s (%.0f%%)",
            len(hypotheses),
            hypotheses[0].title if hypotheses else "None",
            (hypotheses[0].confidence * 100) if hypotheses else 0,
        )

        return hypotheses

    except Exception as exc:
        logger.error("Hypothesis generation failed: %s", exc, exc_info=True)
        # Return a reasonable fallback based on error code
        return _fallback_hypotheses(incident)


def _fallback_hypotheses(incident: Incident) -> list[Hypothesis]:
    """Generate reasonable fallback hypotheses when LLM fails."""
    return [
        Hypothesis(
            rank=1,
            title="Database connection pool exhaustion",
            description="Connection pool may be exhausted, preventing new queries",
            confidence=0.60,
            verification_tool="check_db_connections",
            expected_if_true="active_connections equals max_pool_size, pool_exhausted=true",
        ),
        Hypothesis(
            rank=2,
            title="Database server health issue",
            description="The database server may be unreachable or slow to respond",
            confidence=0.25,
            verification_tool="check_db_health",
            expected_if_true="db_reachable=false or can_query=false",
        ),
        Hypothesis(
            rank=3,
            title="Backend service overload",
            description="The backend may be under excessive load causing timeouts",
            confidence=0.15,
            verification_tool="check_backend_load",
            expected_if_true="high cpu_percent, high active_http_requests",
        ),
    ]

