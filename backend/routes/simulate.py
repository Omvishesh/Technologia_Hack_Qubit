"""
Failure simulation endpoints for controlled incident demonstration.
"""
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from backend.database.connection import db_manager

router = APIRouter(prefix="/simulate", tags=["Failure Simulation"])

class TimeoutSimRequest(BaseModel):
    delay_seconds: float = Field(5.0, description="Delay duration to inject")

class DelaySimRequest(BaseModel):
    delay_seconds: float = Field(5.0, description="Artificial API latency in seconds")

@router.post("/connection-exhaustion")
def simulate_connection_exhaustion(count: Optional[int] = None):
    """
    Primary Demo Scenario:
    Exhausts the database connection pool by acquiring all available connection slots.
    Subsequent /chat requests will immediately fail with 500 PoolTimeoutError.
    """
    db_manager.exhaust_pool(count=count)
    return {
        "status": "incident_injected",
        "scenario": "DATABASE_CONNECTION_EXHAUSTION",
        "message": "Database connection pool saturated. Subsequent DB queries will time out.",
        "pool_status": db_manager.get_pool_status()
    }

@router.post("/db-timeout")
def simulate_db_timeout(req: TimeoutSimRequest = TimeoutSimRequest()):
    """Simulates query timeout by injecting delay on DB executions."""
    db_manager.set_delay(req.delay_seconds)
    return {
        "status": "incident_injected",
        "scenario": "DATABASE_QUERY_TIMEOUT",
        "injected_delay_seconds": req.delay_seconds
    }

@router.post("/db-unavailable")
def simulate_db_unavailable():
    """Simulates complete database unreachability / crash."""
    db_manager.set_unavailable(True)
    return {
        "status": "incident_injected",
        "scenario": "DATABASE_UNAVAILABLE",
        "message": "Database marked unreachable. Queries will throw ConnectionRefusedError."
    }

@router.post("/api-delay")
def simulate_api_delay(req: DelaySimRequest = DelaySimRequest()):
    """Injects heavy artificial latency into API request pipeline."""
    db_manager.set_delay(req.delay_seconds)
    return {
        "status": "incident_injected",
        "scenario": "BACKEND_API_LATENCY",
        "injected_delay_seconds": req.delay_seconds
    }

@router.post("/invalid-sql")
def simulate_invalid_sql():
    """Forces next LLM SQL queries to produce invalid syntax / query errors."""
    db_manager.set_force_invalid_sql(True)
    return {
        "status": "incident_injected",
        "scenario": "INVALID_SQL_QUERY",
        "message": "Next queries will simulate malformed SQL generation."
    }

@router.post("/reset")
def reset_simulations():
    """Resets all injected failures and restores normal system operations."""
    db_manager.clear_pool()
    return {
        "status": "success",
        "message": "All injected failures cleared and connection pool recycled.",
        "pool_status": db_manager.get_pool_status()
    }
