"""
Incident approval and rejection handler endpoints (Human-in-the-Loop integration).
"""
import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.database.connection import db_manager
from backend.app.logger import logger

router = APIRouter(prefix="/incidents", tags=["Incident Approval"])

class ApprovalRequest(BaseModel):
    action: Optional[str] = Field("clear-connection-pool", description="Approved action to execute")
    approved_by: Optional[str] = Field("devops-lead", description="Email or ID of approver")
    notes: Optional[str] = Field(None, description="Approval notes")

class RejectionRequest(BaseModel):
    rejected_by: Optional[str] = Field("devops-lead", description="Email or ID of rejecter")
    reason: Optional[str] = Field("Manual intervention required", description="Rejection reason")

@router.post("/{incident_id}/approve")
def approve_incident_action(incident_id: str, req: ApprovalRequest = ApprovalRequest()):
    """
    Approves the recommended automated remediation action.
    Executes allowlisted tool, verifies recovery, and logs audit record.
    """
    start_t = time.time()

    # Execute approved action
    if req.action in ["clear-connection-pool", "clear_connection_pool"]:
        db_manager.clear_pool()
    elif req.action in ["restart-student-api", "restart_student_api"]:
        db_manager.clear_pool()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported resolution action '{req.action}'.")

    # Post-remediation verification
    health = db_manager.check_health()
    pool_status = db_manager.get_pool_status()

    logger.log_event(
        endpoint=f"/incidents/{incident_id}/approve",
        status=200,
        request_id=f"audit-{incident_id}",
        user_query=f"Action: {req.action}",
        latency_ms=(time.time() - start_t) * 1000,
        extra={
            "approved_by": req.approved_by,
            "post_action_health": health["db_reachable"],
        }
    )

    return {
        "status": "approved_and_executed",
        "incident_id": incident_id,
        "executed_action": req.action,
        "approved_by": req.approved_by,
        "recovered": health["can_query"],
        "database_health": health,
        "pool_status": pool_status
    }

@router.post("/{incident_id}/reject")
def reject_incident_action(incident_id: str, req: RejectionRequest = RejectionRequest()):
    """
    Rejects the proposed resolution action.
    Blocks execution, logs rejection audit trail.
    """
    logger.log_event(
        endpoint=f"/incidents/{incident_id}/reject",
        status=200,
        request_id=f"audit-{incident_id}",
        user_query=f"Rejection reason: {req.reason}",
        extra={
            "rejected_by": req.rejected_by,
            "rejection_reason": req.reason,
        }
    )

    return {
        "status": "rejected",
        "incident_id": incident_id,
        "rejected_by": req.rejected_by,
        "reason": req.reason,
        "action_executed": None,
        "message": "Automated resolution rejected. No changes were applied."
    }
