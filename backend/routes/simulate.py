"""
Failure simulation endpoints for controlled incident demonstration.
"""
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from backend.app.config import settings
from backend.database.connection import db_manager

router = APIRouter(prefix="/simulate", tags=["Failure Simulation"])

class SurgeRequest(BaseModel):
    clients: int = Field(9, ge=1, le=50, description="Simulated concurrent users (default 9 > pool of 5)")
    hold_seconds: float = Field(3.0, ge=0.5, le=30, description="How long each query holds a DB connection")
    duration_seconds: int = Field(300, ge=10, le=3600, description="Auto-stop after this many seconds")

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

@router.post("/traffic-surge")
def simulate_traffic_surge(req: SurgeRequest = SurgeRequest()):
    """
    Legitimate traffic spike: more concurrent users than DB pool slots, so requests
    genuinely queue for a connection and user queries time out. Unlike
    connection-exhaustion (leaked connections -> clear the pool), the right fix here
    is to scale the pool. Stops on /simulate/reset or after duration_seconds.
    """
    db_manager.start_traffic_surge(req.clients, req.hold_seconds, req.duration_seconds)
    return {
        "status": "incident_injected",
        "scenario": "TRAFFIC_SURGE",
        "message": f"{req.clients} simulated users now competing for {settings.DB_POOL_SIZE} DB connections.",
        "clients": req.clients,
        "pool_size": settings.DB_POOL_SIZE,
        "duration_seconds": req.duration_seconds,
    }

@router.post("/reset")
def reset_simulations():
    """Resets all injected failures (incl. traffic surge and pool scaling) and restores normal operations."""
    db_manager.stop_traffic_surge()
    settings.DB_POOL_SIZE = db_manager.default_pool_size
    db_manager.clear_pool()
    return {
        "status": "success",
        "message": "All injected failures cleared, traffic surge stopped, pool size restored and recycled.",
        "pool_status": db_manager.get_pool_status()
    }

