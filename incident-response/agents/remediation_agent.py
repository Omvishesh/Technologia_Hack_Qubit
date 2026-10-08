"""
Agent 5 — Remediation Agent

Proposes a safe remediation action from the allowlist based on the
confirmed root cause.
"""

from __future__ import annotations

import json
import logging

from ..llm_client import call_llm_json
from ..models import Incident, Remediation, RiskLevel
from ..tools.remediation_tools import ALLOWED_REMEDIATION_ACTIONS
from ..error_catalogue import get_catalogue_summary

logger = logging.getLogger("incident-response.agents.remediation_agent")

SYSTEM_PROMPT = """\
You are a remediation specialist for a Student Query API system.

Your task: Based on the confirmed root cause, propose a SINGLE safe remediation action
from the allowlist below.

ALLOWED REMEDIATION TOOLS (you may ONLY propose one of these):
- clear_connection_pool: Drops all held connections and recycles the PostgreSQL connection pool (use for leaked/stale connections)
- restart_student_api: Gracefully restarts the Student Query API service process
- scale_student_api: Dynamically scales up the database pool concurrency capacity (use when legitimate incoming traffic/waiting requests exceed current pool size, e.g. from 5 to 10)

Known error-to-remediation mappings:
{catalogue}

Output ONLY valid JSON with this exact schema:
{{
    "action": "Human-readable description of the remediation action",
    "tool_name": "clear_connection_pool",
    "reason": "Why this specific action addresses the root cause",
    "risk": "LOW",
    "blast_radius": "What services/components are affected by this action",
    "requires_approval": true,
    "estimated_recovery_seconds": 30
}}

A full connection pool has two different causes. Use the VERIFICATION TOOL RESULTS to tell them apart:
- Leaked / stale connections: the pool is full but the backend is quiet —
  active_http_requests is about 0-1 and waiting_requests is about 0-1.
  Fix: clear_connection_pool.
- Genuine traffic demand: more requests in progress than pool slots
  (active_http_requests > max_pool_size) and requests are queuing (waiting_requests > 0).
  Clearing the pool would not help — the traffic refills it immediately. Fix: scale_student_api.

Rules:
1. tool_name MUST be one of: clear_connection_pool, restart_student_api, scale_student_api
2. risk MUST be one of: LOW, MEDIUM, HIGH
3. For a full pool, decide between clear_connection_pool and scale_student_api using the criteria above,
   not the generic error-to-remediation mapping.
4. Be conservative — prefer lower-risk actions when multiple options could work
5. Always set requires_approval to true (human-in-the-loop is mandatory)
"""


async def propose_remediation(incident: Incident) -> Remediation:
    """
    Propose a remediation action based on the confirmed root cause.

    Args:
        incident: The Incident with root_cause populated.

    Returns:
        A Remediation proposal.
    """
    catalogue = get_catalogue_summary()
    system_prompt = SYSTEM_PROMPT.format(catalogue=catalogue)

    user_prompt_parts = [
        f"INCIDENT: {incident.id}",
        f"ERROR: {incident.error_code} — {incident.error_message}",
        "",
    ]

    if incident.root_cause:
        user_prompt_parts.extend([
            "CONFIRMED ROOT CAUSE:",
            f"  Cause: {incident.root_cause.cause}",
            f"  Confidence: {incident.root_cause.confidence:.0%}",
            f"  Evidence: {json.dumps(incident.root_cause.evidence)}",
            "",
        ])

    if incident.verification_results:
        # Measured numbers (pool usage, queued and in-flight requests) — needed to tell
        # leaked connections apart from genuine demand
        user_prompt_parts.append("VERIFICATION TOOL RESULTS:")
        for tr in incident.verification_results:
            outcome = json.dumps(tr.result) if tr.success else f"FAILED: {tr.error}"
            user_prompt_parts.append(f"  {tr.tool_name}: {outcome}")
        user_prompt_parts.append("")

    if incident.log_summary:
        user_prompt_parts.extend([
            "LOG SUMMARY:",
            f"  {incident.log_summary.summary}",
            "",
        ])

    user_prompt = "\n".join(user_prompt_parts)

    logger.info("Proposing remediation for incident %s", incident.id)

    try:
        result = await call_llm_json(system_prompt, user_prompt)

        tool_name = result.get("tool_name", "restart_student_api")

        # Enforce allowlist
        if tool_name not in ALLOWED_REMEDIATION_ACTIONS:
            logger.warning(
                "LLM proposed disallowed tool '%s', falling back to restart_student_api",
                tool_name,
            )
            tool_name = "restart_student_api"

        remediation = Remediation(
            action=result.get("action", f"Execute {tool_name}"),
            tool_name=tool_name,
            reason=result.get("reason", "Proposed by remediation agent"),
            risk=RiskLevel(result.get("risk", "LOW")),
            blast_radius=result.get("blast_radius", "Student Query API only"),
            requires_approval=True,  # Always require human approval
            estimated_recovery_seconds=int(result.get("estimated_recovery_seconds", 30)),
        )

        logger.info(
            "Remediation proposed: '%s' via %s (risk: %s)",
            remediation.action,
            remediation.tool_name,
            remediation.risk,
        )

        return remediation

    except Exception as exc:
        logger.error("Remediation proposal failed: %s", exc, exc_info=True)
        # Safe fallback
        return Remediation(
            action="Restart Student Query API",
            tool_name="restart_student_api",
            reason=f"Default fallback remediation (LLM failed: {exc})",
            risk=RiskLevel.LOW,
            blast_radius="Student Query API only",
            requires_approval=True,
        )

