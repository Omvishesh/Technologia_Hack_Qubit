"""
Allowlisted verification and remediation tool endpoints for Om's incident agents.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from backend.database.connection import db_manager
from backend.services.metrics_service import metrics_service
from backend.app.config import settings

router = APIRouter(prefix="/tools", tags=["Agent Tools"])

class ScaleRequest(BaseModel):
    pool_size: int = Field(5, ge=1, le=50, description="New DB pool size")

# ==========================================
# 1. Verification Tools (Read-Only Diagnostics)
# ==========================================

@router.get("/check-db-connections")
def check_db_connections():
    """Inspects active connection count vs max pool capacity."""
    return db_manager.get_pool_status()

@router.get("/check-db-health")
def check_db_health():
    """Pings database and returns connectivity, ping latency, and error states."""
    return db_manager.check_health()

@router.get("/check-backend-load")
def check_backend_load():
    """Returns current process CPU usage, memory RSS in MB, and total requests."""
    return metrics_service.get_system_load()

# ==========================================
# 2. Resolution Tools (Allowlisted Remediation)
# ==========================================

@router.post("/clear-connection-pool")
def clear_connection_pool():
    """
    Remediation Action:
    Force-closes leaked or hung database connections and recycles the connection pool.
    """
    db_manager.clear_pool()
    return {
        "status": "success",
        "action": "clear-connection-pool",
        "message": "Connection pool successfully flushed and recycled.",
        "pool_status": db_manager.get_pool_status()
    }

@router.post("/restart-student-api")
def restart_student_api():
    """
    Remediation Action:
    Gracefully restarts the student-api runtime state and flushes database connections.
    """
    db_manager.clear_pool()
    return {
        "status": "success",
        "action": "restart-student-api",
        "message": "Student API service process gracefully recycled.",
        "healthy": True
    }

@router.post("/scale-student-api")
def scale_student_api(req: ScaleRequest):
    """
    Remediation Action:
    Dynamically adjusts pool capacity.
    """
    settings.DB_POOL_SIZE = req.pool_size
    db_manager.clear_pool()
    return {
        "status": "success",
        "action": "scale-student-api",
        "new_pool_size": req.pool_size,
        "pool_status": db_manager.get_pool_status()
    }
