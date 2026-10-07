"""
Health, Metrics, and Student Direct Inspection Routes.
"""
from typing import Optional
from fastapi import APIRouter, Query
from backend.database.connection import db_manager
from backend.services.metrics_service import metrics_service

router = APIRouter(tags=["Health & Metrics"])

@router.get("/health")
def health_check():
    """Liveness & DB connectivity probe."""
    db_health = db_manager.check_health()
    status_str = "healthy" if db_health["can_query"] else "degraded"
    return {
        "status": status_str,
        "service": "student-api",
        "database": db_health
    }

@router.get("/metrics")
def get_metrics():
    """Returns request rate, error rate, latency, and DB pool stats."""
    pool_status = db_manager.get_pool_status()
    return metrics_service.get_metrics(pool_status)

@router.get("/students")
def get_students(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    department: Optional[str] = None
):
    """Direct inspection endpoint for student records."""
    if department:
        query = f"SELECT * FROM students WHERE department = '{department}' LIMIT {limit} OFFSET {offset};"
    else:
        query = f"SELECT * FROM students LIMIT {limit} OFFSET {offset};"
    
    rows = db_manager.execute_query(query)
    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "students": rows
    }
