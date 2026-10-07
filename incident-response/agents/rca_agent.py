"""
Agent 4 — Root Cause Analyzer (RCA)

Combines logs, hypotheses, and verification tool results to confirm
the most-supported root cause with evidence and confidence.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..llm_client import call_llm_json
from ..models import Incident, RootCause

logger = logging.getLogger("incident-response.agents.rca_agent")

SYSTEM_PROMPT = """\
You are a senior incident response analyst. Your task is to determine the confirmed root cause
of an incident based on:
1. The original error and log analysis
2. Three ranked hypotheses
3. Verification tool results for each hypothesis

Analyze the evidence from the tool results against each hypothesis's expected outcome.
Determine which hypothesis is best supported by the actual data.

Output ONLY valid JSON with this exact schema:
{
    "cause": "Clear statement of the confirmed root cause",
    "evidence": [
        "Evidence point 1 from tool results",
        "Evidence point 2 from tool results",
        "Evidence point 3 from tool results"
    ],
    "confidence": 0.94,
    "confirmed_hypothesis_rank": 1,
    "supporting_data": {
        "key_metric_1": "value",
        "key_metric_2": "value"
    }
}

Rules:
1. Confidence should reflect how strongly the tool results support the conclusion.
2. Evidence items must reference actual values from the tool results, not hypotheticals.
3. confirmed_hypothesis_rank must be 1, 2, or 3.
4. If no hypothesis is clearly supported, pick the most likely and lower the confidence.
"""


async def analyze_root_cause(incident: Incident) -> RootCause:
    """
    Determine the confirmed root cause from hypotheses and verification results.

    Args:
        incident: The Incident with hypotheses and verification_results populated.

    Returns:
        A RootCause object with the confirmed cause, evidence, and confidence.
    """
    # Build user prompt with all context
    user_prompt_parts = [
        f"INCIDENT: {incident.id}",
        f"ERROR: {incident.error_code} — {incident.error_message}",
        "",
        "LOG ANALYSIS:",
        incident.log_summary.summary if incident.log_summary else "N/A",
        "",
        "HYPOTHESES:",
    ]

    for h in incident.hypotheses:
        user_prompt_parts.append(
            f"  #{h.rank} [{h.confidence:.0%}] {h.title}\n"
            f"    Description: {h.description}\n"
            f"    Verification tool: {h.verification_tool}\n"
            f"    Expected if true: {h.expected_if_true}"
        )

    user_prompt_parts.append("")
    user_prompt_parts.append("VERIFICATION TOOL RESULTS:")

    for tr in incident.verification_results:
        user_prompt_parts.append(
            f"  Tool: {tr.tool_name}\n"
            f"  Success: {tr.success}\n"
            f"  Result: {json.dumps(tr.result, default=str)}\n"
            f"  Error: {tr.error or 'None'}"
        )

    user_prompt = "\n".join(user_prompt_parts)

    logger.info("Analyzing root cause for incident %s", incident.id)

    try:
        result = await call_llm_json(SYSTEM_PROMPT, user_prompt)

        root_cause = RootCause(
            cause=result["cause"],
            evidence=result.get("evidence", []),
            confidence=float(result.get("confidence", 0.5)),
            confirmed_hypothesis_rank=int(result.get("confirmed_hypothesis_rank", 1)),
            supporting_data=result.get("supporting_data", {}),
        )

        logger.info(
            "Root cause confirmed: '%s' (confidence: %.0f%%, hypothesis #%d)",
            root_cause.cause,
            root_cause.confidence * 100,
            root_cause.confirmed_hypothesis_rank,
        )

        return root_cause

    except Exception as exc:
        logger.error("RCA analysis failed: %s", exc, exc_info=True)
        # Fallback: pick the highest-confidence hypothesis
        top = incident.hypotheses[0] if incident.hypotheses else None
        return RootCause(
            cause=top.title if top else incident.error_message or "Unknown",
            evidence=[f"Fallback: LLM analysis failed ({exc})"],
            confidence=0.5,
            confirmed_hypothesis_rank=1,
        )

