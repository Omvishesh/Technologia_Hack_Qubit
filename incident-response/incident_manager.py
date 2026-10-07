"""
Incident Manager — The main orchestrator for the incident response pipeline.

Chains all agents in sequence:
  detect → collect logs/metrics → analyze → hypothesize → verify → 
  confirm root cause → propose remediation → safety check → send email →
  (await approval) → execute resolution → verify recovery

Also maintains an in-memory incident store for the API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .config import get_settings
from .models import Incident, IncidentStatus, IncidentReport, RecoveryResult
from .timeline import add_event, format_timeline

# Agents
from .agents.log_analyzer import analyze_logs
from .agents.hypothesis_generator import generate_hypotheses
from .agents.verification_executor import execute_verifications
from .agents.rca_agent import analyze_root_cause
from .agents.remediation_agent import propose_remediation
from .agents.safety_agent import check_safety

# Tools
from .tools.log_collector import collect_logs
from .tools.metrics_collector import collect_metrics, parse_metrics_snapshot
from .tools.remediation_tools import call_remediation_tool

# Email & Recovery
from .email_sender import send_approval_email, send_resolution_email
from .recovery import verify_recovery

logger = logging.getLogger("incident-response.manager")


# ─────────────────────────────────────────────────────────────
# In-memory incident store
# ─────────────────────────────────────────────────────────────

_incidents: dict[str, Incident] = {}


def get_incident(incident_id: str) -> Incident | None:
    """Retrieve an incident by ID."""
    return _incidents.get(incident_id)


def get_all_incidents() -> list[Incident]:
    """Retrieve all incidents, newest first."""
    return sorted(_incidents.values(), key=lambda i: i.created_at, reverse=True)


def store_incident(incident: Incident) -> None:
    """Store or update an incident in the store."""
    _incidents[incident.id] = incident


_TERMINAL = {IncidentStatus.RESOLVED, IncidentStatus.REJECTED, IncidentStatus.RECOVERY_FAILED}
_WITH_HUMAN = {IncidentStatus.AWAITING_APPROVAL, IncidentStatus.APPROVED, IncidentStatus.RESOLVING}


def get_open_incident(stale_after_seconds: int = 300) -> Incident | None:
    """
    The newest incident still being handled, if any — detectors use this so one
    outage produces one incident (and one approval email).

    Incidents waiting on the engineer or mid-remediation always count. An analysis
    stage that hasn't progressed for `stale_after_seconds` (e.g. the pipeline
    crashed) doesn't, so it can't block detection forever.
    """
    now = datetime.now(timezone.utc)
    for inc in get_all_incidents():
        if inc.status in _TERMINAL:
            continue
        if inc.status in _WITH_HUMAN or (now - inc.updated_at).total_seconds() < stale_after_seconds:
            return inc
    return None


def close_self_recovered(detected_by: str) -> list[Incident]:
    """
    Close incidents raised by `detected_by` that are still awaiting approval although
    the service has since recovered on its own (e.g. the backend was briefly
    unreachable during a deploy). No remediation is executed. Without this the stale
    incident stays open and makes the detectors ignore the next real outage.
    """
    closed = []
    for inc in get_all_incidents():
        if inc.detected_by != detected_by or inc.status != IncidentStatus.AWAITING_APPROVAL:
            continue
        inc.status = IncidentStatus.RESOLVED
        inc.resolved_at = datetime.now(timezone.utc)
        inc.recovery = RecoveryResult(
            recovered=True,
            health_check_passed=True,
            db_connected=True,
            details="Service recovered on its own — no remediation executed",
        )
        add_event(inc, "recovery", "Service recovered without intervention; incident closed automatically (no remediation executed)")
        store_incident(inc)
        logger.info("Closed %s: service recovered on its own", inc.id)
        closed.append(inc)
    return closed


def last_closed_at() -> datetime | None:
    """When the most recent finished incident was closed (resolved / rejected / failed)."""
    closed = [inc.resolved_at or inc.updated_at for inc in _incidents.values() if inc.status in _TERMINAL]
    return max(closed, default=None)


# ─────────────────────────────────────────────────────────────
# Full pipeline orchestration
# ─────────────────────────────────────────────────────────────

async def run_pipeline(incident: Incident) -> Incident:
    """
    Run the complete incident response pipeline from detection through
    email approval.

    This function handles steps 1-7 of the pipeline:
    1. Collect logs and metrics
    2. Analyze logs (Agent 1)
    3. Generate hypotheses (Agent 2)
    4. Execute verifications (Agent 3)
    5. Confirm root cause (Agent 4)
    6. Propose remediation (Agent 5)
    7. Safety check (Agent 6)
    8. Send approval email

    Steps after this (approval, resolution, recovery) are triggered
    by the API endpoints.

    Args:
        incident: A freshly detected Incident.

    Returns:
        The fully analyzed Incident awaiting approval.
    """
    store_incident(incident)
    logger.info("═══ PIPELINE START: %s ═══", incident.id)

    try:
        # ── Step 1: Collect logs and metrics ─────────────────
        incident.status = IncidentStatus.ANALYZING
        add_event(incident, "collection", "Collecting logs and metrics from backend")

        logs_result = await collect_logs(limit=100)
        if logs_result["success"]:
            incident.raw_logs = logs_result["logs"]
            add_event(
                incident, "collection",
                f"Collected {logs_result['count']} log entries",
                {"log_count": logs_result["count"]},
            )
        else:
            add_event(
                incident, "collection",
                f"Log collection failed: {logs_result['error']}",
                {"error": logs_result["error"]},
            )

        metrics_result = await collect_metrics()
        if metrics_result["success"]:
            incident.metrics = parse_metrics_snapshot(metrics_result["metrics"])
            add_event(incident, "collection", "Metrics collected successfully")
        else:
            add_event(
                incident, "collection",
                f"Metrics collection failed: {metrics_result['error']}",
            )

        # ── Step 2: Log Analysis (Agent 1) ───────────────────
        add_event(incident, "log_analysis", "Starting LLM log analysis")
        incident.log_summary = await analyze_logs(incident)
        add_event(
            incident, "log_analysis",
            f"Log analysis complete: {incident.log_summary.summary[:100]}...",
            {
                "error_signals": incident.log_summary.error_signals,
                "dominant_error": incident.log_summary.dominant_error,
            },
        )

        # ── Step 3: Hypothesis Generation (Agent 2) ──────────
        incident.status = IncidentStatus.HYPOTHESES_GENERATED
        add_event(incident, "hypothesis", "Generating root-cause hypotheses")
        incident.hypotheses = await generate_hypotheses(incident)
        add_event(
            incident, "hypothesis",
            f"Generated {len(incident.hypotheses)} hypotheses. "
            f"Top: {incident.hypotheses[0].title} ({incident.hypotheses[0].confidence:.0%})",
            {"hypotheses": [h.model_dump() for h in incident.hypotheses]},
        )

        # ── Step 4: Verification (Agent 3) ───────────────────
        incident.status = IncidentStatus.VERIFYING
        add_event(incident, "verification", "Executing verification tools")
        incident.verification_results = await execute_verifications(incident)
        add_event(
            incident, "verification",
            f"Verification complete: {sum(1 for r in incident.verification_results if r.success)}"
            f"/{len(incident.verification_results)} tools succeeded",
            {"results": [r.model_dump() for r in incident.verification_results]},
        )

        # ── Step 5: Root Cause Analysis (Agent 4) ────────────
        incident.status = IncidentStatus.ROOT_CAUSE_CONFIRMED
        add_event(incident, "rca", "Analyzing root cause from evidence")
        incident.root_cause = await analyze_root_cause(incident)
        add_event(
            incident, "rca",
            f"Root cause confirmed: {incident.root_cause.cause} "
            f"(confidence: {incident.root_cause.confidence:.0%})",
            {"root_cause": incident.root_cause.model_dump()},
        )

        # ── Step 6: Remediation Proposal (Agent 5) ───────────
        incident.status = IncidentStatus.REMEDIATION_PROPOSED
        add_event(incident, "remediation", "Proposing remediation action")
        incident.remediation = await propose_remediation(incident)
        add_event(
            incident, "remediation",
            f"Proposed: {incident.remediation.action} "
            f"via {incident.remediation.tool_name} (risk: {incident.remediation.risk.value})",
            {"remediation": incident.remediation.model_dump()},
        )

        # ── Step 7: Safety Check (Agent 6) ───────────────────
        incident.status = IncidentStatus.SAFETY_CHECKED
        add_event(incident, "safety", "Running safety checks")
        incident.safety_check = await check_safety(incident)

        if incident.safety_check.allowed:
            add_event(
                incident, "safety",
                "Safety check PASSED — all rules satisfied",
                {"safety": incident.safety_check.model_dump()},
            )
        else:
            add_event(
                incident, "safety",
                f"Safety check FAILED: {incident.safety_check.rejection_reason}",
                {"safety": incident.safety_check.model_dump()},
            )
            # Even if safety fails, we continue to allow manual review
            logger.warning("Safety check failed but continuing for manual review")

        # ── Step 8: Send Approval Email ──────────────────────
        incident.status = IncidentStatus.AWAITING_APPROVAL
        add_event(incident, "email", "Sending approval email to DevOps engineer")
        email_sent = await send_approval_email(incident)
        add_event(
            incident, "email",
            f"Email {'sent' if email_sent else 'FAILED'}",
            {"email_sent": email_sent},
        )

        store_incident(incident)

        logger.info("═══ PIPELINE COMPLETE: %s ═══", incident.id)
        logger.info("Status: %s", incident.status.value)
        logger.info("Timeline:\n%s", format_timeline(incident))

        return incident

    except Exception as exc:
        logger.error("Pipeline failed for %s: %s", incident.id, exc, exc_info=True)
        add_event(incident, "error", f"Pipeline failed: {exc}")
        store_incident(incident)
        raise


# ─────────────────────────────────────────────────────────────
# Post-approval actions
# ─────────────────────────────────────────────────────────────

async def approve_incident(incident_id: str, approved_by: str = "devops") -> Incident:
    """
    Handle approval: execute remediation and verify recovery.

    Args:
        incident_id: The incident to approve.
        approved_by: Who approved it.

    Returns:
        Updated Incident.

    Raises:
        ValueError: If incident not found or not in correct state.
    """
    incident = get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    if incident.status != IncidentStatus.AWAITING_APPROVAL:
        raise ValueError(
            f"Incident {incident_id} is in state '{incident.status.value}', "
            f"expected 'awaiting_approval'"
        )

    # Record approval
    incident.status = IncidentStatus.APPROVED
    incident.approved_by = approved_by
    incident.approval_timestamp = datetime.now(timezone.utc)
    add_event(incident, "approval", f"Approved by {approved_by}")

    # Execute remediation tool
    incident.status = IncidentStatus.RESOLVING
    tool_name = incident.remediation.tool_name if incident.remediation else "restart_student_api"
    add_event(incident, "resolution", f"Executing remediation tool: {tool_name}")

    try:
        # Capture pre-remediation metrics for comparison
        pre_metrics_raw = await collect_metrics()
        pre_metrics = pre_metrics_raw.get("metrics", {}) if pre_metrics_raw.get("success") else None

        tool_kwargs = {}
        if tool_name == "scale_student_api":
            # Scale up pool to 10 connections to accommodate surge
            tool_kwargs["pool_size"] = 10

        resolution_result = await call_remediation_tool(tool_name, **tool_kwargs)
        add_event(
            incident, "resolution",
            f"Tool '{tool_name}' executed: success={resolution_result.success}",
            {"result": resolution_result.model_dump()},
        )

        if not resolution_result.success:
            incident.status = IncidentStatus.RECOVERY_FAILED
            add_event(incident, "resolution", f"Remediation failed: {resolution_result.error}")
            store_incident(incident)
            return incident

        # Verify recovery
        add_event(incident, "recovery", "Verifying service recovery...")
        recovery_result = await verify_recovery(
            wait_seconds=incident.remediation.estimated_recovery_seconds if incident.remediation else 10,
            pre_metrics=pre_metrics,
        )
    except Exception as exc:
        # Never leave the incident stuck in RESOLVING: that counts as "open" and
        # would stop the detectors from raising the next outage.
        logger.error("Post-approval pipeline failed for %s: %s", incident_id, exc, exc_info=True)
        incident.status = IncidentStatus.RECOVERY_FAILED
        add_event(incident, "error", f"Remediation/recovery step failed: {exc}")
        store_incident(incident)
        return incident
    incident.recovery = recovery_result

    if recovery_result.recovered:
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(timezone.utc)
        add_event(
            incident, "recovery",
            f"✅ INCIDENT RESOLVED — {recovery_result.details}",
            {"recovery": recovery_result.model_dump()},
        )
        # Dispatch resolution confirmation email to DevOps engineer
        await send_resolution_email(incident)
        add_event(incident, "email", "Resolution confirmation email dispatched to engineer")
    else:
        incident.status = IncidentStatus.RECOVERY_FAILED
        add_event(
            incident, "recovery",
            f"❌ Recovery failed — {recovery_result.details}",
            {"recovery": recovery_result.model_dump()},
        )

    store_incident(incident)
    logger.info("Post-approval pipeline complete for %s: %s", incident_id, incident.status.value)
    return incident


async def reject_incident(incident_id: str, reason: str = "", rejected_by: str = "devops") -> Incident:
    """
    Handle rejection of a proposed remediation.

    Args:
        incident_id: The incident to reject.
        reason: Why the engineer rejected it.
        rejected_by: Who rejected it.

    Returns:
        Updated Incident.

    Raises:
        ValueError: If incident not found or not in correct state.
    """
    incident = get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    if incident.status != IncidentStatus.AWAITING_APPROVAL:
        raise ValueError(
            f"Incident {incident_id} is in state '{incident.status.value}', "
            f"expected 'awaiting_approval'"
        )

    incident.status = IncidentStatus.REJECTED
    incident.rejection_reason = reason or "Rejected by engineer"
    add_event(
        incident, "rejection",
        f"Rejected by {rejected_by}: {reason or 'No reason provided'}",
    )

    store_incident(incident)
    logger.info("Incident %s REJECTED by %s", incident_id, rejected_by)
    return incident

