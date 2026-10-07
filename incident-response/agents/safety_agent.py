"""
Agent 6 — Safety / Permission Layer

Validates the proposed remediation against the allowlist and safety rules.
This is a mandatory control gate — NO action can be executed without
passing this layer.

This agent does NOT use LLM. It is a deterministic rule-based check.
"""

from __future__ import annotations

import logging

from ..models import Incident, Remediation, SafetyCheck
from ..tools.remediation_tools import ALLOWED_REMEDIATION_ACTIONS

logger = logging.getLogger("incident-response.agents.safety_agent")

# ─────────────────────────────────────────────────────────────
# Allowlists and rules
# ─────────────────────────────────────────────────────────────

ALLOWED_ACTIONS: set[str] = ALLOWED_REMEDIATION_ACTIONS

ALLOWED_TARGET_SERVICES: set[str] = {
    "student-api",
    "student-query-api",
    "Student Query API",
}

ACCEPTABLE_BLAST_RADIUS_KEYWORDS: set[str] = {
    "student",
    "api",
    "query",
    "only",
}

# Actions that are NEVER allowed regardless of context
BLOCKED_ACTIONS: set[str] = {
    "delete_database",
    "modify_student_records",
    "restart_entire_vm",
    "execute_arbitrary_shell",
    "drop_table",
    "truncate_table",
    "rm_rf",
}


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

async def check_safety(incident: Incident) -> SafetyCheck:
    """
    Validate the proposed remediation against safety rules.

    This is a deterministic check — no LLM involved.

    Args:
        incident: The Incident with remediation populated.

    Returns:
        A SafetyCheck result indicating whether the action is allowed.
    """
    remediation = incident.remediation

    if remediation is None:
        return SafetyCheck(
            allowed=False,
            action="None",
            target_service=incident.service,
            is_action_allowlisted=False,
            is_blast_radius_acceptable=False,
            requires_human_approval=True,
            rejection_reason="No remediation action proposed",
        )

    # ── Check 1: Is the action explicitly blocked? ───────────
    if remediation.tool_name in BLOCKED_ACTIONS:
        logger.warning(
            "SAFETY BLOCKED: '%s' is in the blocked actions list",
            remediation.tool_name,
        )
        return SafetyCheck(
            allowed=False,
            action=remediation.tool_name,
            target_service=incident.service,
            is_action_allowlisted=False,
            is_blast_radius_acceptable=False,
            requires_human_approval=True,
            rejection_reason=f"Action '{remediation.tool_name}' is explicitly blocked",
        )

    # ── Check 2: Is the action in the allowlist? ─────────────
    is_allowlisted = remediation.tool_name in ALLOWED_ACTIONS

    # ── Check 3: Is the target service allowed? ──────────────
    is_target_ok = incident.service.lower() in {s.lower() for s in ALLOWED_TARGET_SERVICES}

    # ── Check 4: Is the blast radius acceptable? ─────────────
    blast_lower = remediation.blast_radius.lower()
    is_blast_ok = any(kw in blast_lower for kw in ACCEPTABLE_BLAST_RADIUS_KEYWORDS)

    # ── Final decision ───────────────────────────────────────
    allowed = is_allowlisted and is_target_ok and is_blast_ok
    rejection_reason = None

    if not allowed:
        reasons = []
        if not is_allowlisted:
            reasons.append(f"Action '{remediation.tool_name}' not in allowlist {ALLOWED_ACTIONS}")
        if not is_target_ok:
            reasons.append(f"Target service '{incident.service}' not in allowed services")
        if not is_blast_ok:
            reasons.append(f"Blast radius '{remediation.blast_radius}' not acceptable")
        rejection_reason = "; ".join(reasons)

    safety_check = SafetyCheck(
        allowed=allowed,
        action=remediation.tool_name,
        target_service=incident.service,
        is_action_allowlisted=is_allowlisted,
        is_blast_radius_acceptable=is_blast_ok,
        requires_human_approval=True,  # Always require human approval
        rejection_reason=rejection_reason,
    )

    if allowed:
        logger.info(
            "SAFETY PASSED: '%s' on '%s' — all checks OK, awaiting human approval",
            remediation.tool_name,
            incident.service,
        )
    else:
        logger.warning(
            "SAFETY REJECTED: '%s' — %s",
            remediation.tool_name,
            rejection_reason,
        )

    return safety_check

