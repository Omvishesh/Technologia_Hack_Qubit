"""
Incident Response API — FastAPI service on port 8001.

Provides endpoints for:
- Listing and viewing incidents
- Approval / Rejection (called from email buttons)
- Manually triggering the pipeline
- Incident timeline
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import get_settings
from .models import Incident, IncidentStatus, Severity
from .incident_manager import (
    get_incident,
    get_all_incidents,
    store_incident,
    run_pipeline,
    approve_incident,
    reject_incident,
)
from .detector import IncidentDetector
from .log_monitor import LogMonitor
from .timeline import format_timeline

logger = logging.getLogger("incident-response.api")

# ─────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Incident Response System",
    description="Multi-Agent Incident Response Pipeline API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Detectors (started on app startup): /health + /metrics poller, and the log-file monitor
_detector: IncidentDetector | None = None
_log_monitor: LogMonitor | None = None


# ─────────────────────────────────────────────────────────────
# Request/Response schemas
# ─────────────────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    error_code: str = "DB_CONNECTION_EXHAUSTION"
    error_message: str = "Manually triggered incident for testing"
    severity: str = "HIGH"


class ApprovalRequest(BaseModel):
    approved_by: str = "devops-engineer"


class RejectionRequest(BaseModel):
    reason: str = ""
    rejected_by: str = "devops-engineer"


# ─────────────────────────────────────────────────────────────
# Lifecycle events
# ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Start the incident detector polling loop and the log monitor."""
    global _detector, _log_monitor

    async def on_incident(incident: Incident):
        logger.info("Auto-detected incident: %s", incident.id)
        await run_pipeline(incident)

    _detector = IncidentDetector(on_incident=on_incident)
    # Start detector in background
    asyncio.create_task(_detector.start())
    if get_settings().log_monitor_enabled:
        _log_monitor = LogMonitor(on_incident=on_incident)
        asyncio.create_task(_log_monitor.start())
    logger.info("Incident Response API started on port %s", get_settings().incident_service_port)


@app.on_event("shutdown")
async def shutdown():
    """Stop the detector and the log monitor."""
    if _detector:
        _detector.stop()
    if _log_monitor:
        _log_monitor.stop()


@app.get("/monitor")
async def monitor_status():
    """Log monitor status: where it reads from, lines seen, incidents raised."""
    if _log_monitor is None:
        return {"running": False, "reason": "LOG_MONITOR_ENABLED is false"}
    return _log_monitor.status()


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Service info."""
    return {
        "service": "incident-response-system",
        "version": "0.1.0",
        "status": "running",
        "incidents_count": len(get_all_incidents()),
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "incident-response"}


# ── Incident listing ────────────────────────────────────────

@app.get("/incidents")
async def list_incidents():
    """List all incidents."""
    incidents = get_all_incidents()
    return {
        "count": len(incidents),
        "incidents": [
            {
                "id": inc.id,
                "service": inc.service,
                "severity": inc.severity.value,
                "status": inc.status.value,
                "error_code": inc.error_code,
                "error_message": inc.error_message,
                "created_at": inc.created_at.isoformat(),
                "updated_at": inc.updated_at.isoformat(),
            }
            for inc in incidents
        ],
    }


@app.get("/incidents/{incident_id}")
async def get_incident_detail(incident_id: str):
    """Get full incident details."""
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    return incident.model_dump(mode="json")


@app.get("/incidents/{incident_id}/timeline")
async def get_incident_timeline(incident_id: str):
    """Get formatted incident timeline."""
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    return {
        "incident_id": incident_id,
        "status": incident.status.value,
        "timeline_formatted": format_timeline(incident),
        "timeline": [
            {
                "timestamp": e.timestamp.isoformat(),
                "stage": e.stage,
                "description": e.description,
                "data": e.data,
            }
            for e in incident.timeline
        ],
    }


# ── Manual trigger ───────────────────────────────────────────

@app.post("/incidents/trigger")
async def trigger_incident(req: TriggerRequest, background_tasks: BackgroundTasks):
    """
    Manually trigger the incident pipeline (for testing / demo).

    Creates an incident and runs the full pipeline in the background.
    """
    incident = Incident(
        error_code=req.error_code,
        error_message=req.error_message,
        severity=Severity(req.severity),
        status=IncidentStatus.DETECTED,
    )
    incident.add_timeline_event(
        "detection",
        f"Incident manually triggered: {req.error_code}",
    )

    store_incident(incident)

    # Run pipeline in background so the API responds immediately
    background_tasks.add_task(run_pipeline, incident)

    return {
        "message": "Incident pipeline triggered",
        "incident_id": incident.id,
        "status": incident.status.value,
    }


# ── Approval / Rejection ────────────────────────────────────

@app.post("/incidents/{incident_id}/approve")
async def approve(incident_id: str, req: ApprovalRequest | None = None):
    """
    Approve the proposed remediation.

    Called when the DevOps engineer clicks APPROVE in the email.
    Executes the resolution tool and verifies recovery.
    """
    approved_by = req.approved_by if req else "devops-engineer"

    try:
        incident = await approve_incident(incident_id, approved_by=approved_by)
        return {
            "message": "Remediation approved and executed",
            "incident_id": incident.id,
            "status": incident.status.value,
            "recovery": incident.recovery.model_dump() if incident.recovery else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/incidents/{incident_id}/approve")
async def approve_get(incident_id: str):
    """
    GET version of approve — for email button links.

    Redirects to a simple HTML confirmation page.
    """
    try:
        incident = await approve_incident(incident_id)
        status = "✅ RESOLVED" if incident.status == IncidentStatus.RESOLVED else "⚠️ " + incident.status.value
        html = f"""
        <html>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>{status}</h1>
            <p>Incident <strong>{incident_id}</strong> has been approved.</p>
            <p>Status: <strong>{incident.status.value}</strong></p>
            <p>{incident.recovery.details if incident.recovery else ''}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    except ValueError as exc:
        return HTMLResponse(
            content=f"<h1>Error</h1><p>{exc}</p>",
            status_code=400,
        )


@app.post("/incidents/{incident_id}/reject")
async def reject(incident_id: str, req: RejectionRequest | None = None):
    """
    Reject the proposed remediation.

    Called when the DevOps engineer clicks REJECT in the email.
    """
    reason = req.reason if req else ""
    rejected_by = req.rejected_by if req else "devops-engineer"

    try:
        incident = await reject_incident(incident_id, reason=reason, rejected_by=rejected_by)
        return {
            "message": "Remediation rejected",
            "incident_id": incident.id,
            "status": incident.status.value,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/incidents/{incident_id}/reject")
async def reject_get(incident_id: str):
    """GET version of reject — for email button links."""
    try:
        incident = await reject_incident(incident_id)
        html = f"""
        <html>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>❌ Remediation Rejected</h1>
            <p>Incident <strong>{incident_id}</strong> remediation has been rejected.</p>
            <p>The incident remains open for manual investigation.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    except ValueError as exc:
        return HTMLResponse(
            content=f"<h1>Error</h1><p>{exc}</p>",
            status_code=400,
        )


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def start_server():
    """Start the API server (for direct invocation)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "incident-response.api:app",
        host=settings.incident_service_host,
        port=settings.incident_service_port,
        reload=settings.is_debug,
    )


if __name__ == "__main__":
    start_server()

