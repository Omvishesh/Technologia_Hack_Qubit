"""
Application log inspection endpoint.
Allows incident detection agents to tail and filter structured logs.
"""
from typing import Optional
from fastapi import APIRouter, Query
from backend.app.logger import logger

router = APIRouter(tags=["Logs"])

@router.get("/logs")
def get_logs(
    limit: int = Query(50, ge=1, le=500, description="Max number of log lines to tail"),
    status: Optional[int] = Query(None, description="Filter logs by HTTP status code, e.g., 500")
):
    """Retrieve structured JSON application logs."""
    entries = logger.read_logs(limit=limit, status=status)
    return {
        "count": len(entries),
        "status_filter": status,
        "logs": entries
    }
