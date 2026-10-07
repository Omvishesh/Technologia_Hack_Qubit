"""
Lightweight mock server for Saket's Student API backend (Port 8000).
Used for local smoke testing while Saket is finalizing the real backend.

Provides:
- GET /health
- GET /metrics
- GET /logs
- GET /tools/check-db-connections
- GET /tools/check-db-health
- GET /tools/check-backend-load
- POST /tools/clear-connection-pool
- POST /tools/restart-student-api
"""

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Mock Student API")

# Simulated state
is_exhausted = True

@app.get("/health")
def health():
    if is_exhausted:
        return {"status": "degraded", "healthy": False, "db_reachable": True, "can_query": False, "error": "PoolTimeoutError"}
    return {"status": "ok", "healthy": True, "db_reachable": True, "can_query": True}

@app.get("/metrics")
def metrics():
    if is_exhausted:
        return {
            "cpu_percent": 24.5,
            "memory_mb": 195.0,
            "active_http_requests": 14,
            "db_pool_active": 10,
            "db_pool_max": 10,
            "error_rate": 0.85,
            "avg_latency_ms": 3120.0
        }
    return {
        "cpu_percent": 12.0,
        "memory_mb": 140.0,
        "active_http_requests": 2,
        "db_pool_active": 1,
        "db_pool_max": 10,
        "error_rate": 0.01,
        "avg_latency_ms": 110.0
    }

@app.get("/logs")
def logs(limit: int = 50):
    if is_exhausted:
        return {
            "success": True,
            "logs": [
                {
                    "timestamp": "2026-10-07T14:15:30.124Z",
                    "service": "student-api",
                    "request_id": "req-98213f",
                    "endpoint": "/chat",
                    "user_query": "which student has cgpa greater than 8",
                    "db_pool_active": 10,
                    "db_pool_max": 10,
                    "status": 500,
                    "error": "asyncpg.exceptions.PoolTimeoutError: Timeout waiting for connection from pool after 3.0s",
                    "latency_ms": 3005
                },
                {
                    "timestamp": "2026-10-07T14:15:33.200Z",
                    "service": "student-api",
                    "request_id": "req-98214a",
                    "endpoint": "/chat",
                    "status": 500,
                    "error": "asyncpg.exceptions.PoolTimeoutError: Timeout waiting for connection from pool after 3.0s",
                    "latency_ms": 3010
                }
            ]
        }
    return {"success": True, "logs": [{"status": 200, "endpoint": "/health"}]}

@app.get("/tools/check-db-connections")
def check_db_connections():
    return {
        "active_connections": 10 if is_exhausted else 1,
        "max_pool_size": 10,
        "waiting_requests": 9 if is_exhausted else 0,
        "pool_exhausted": is_exhausted
    }

@app.get("/tools/check-db-health")
def check_db_health():
    return {
        "db_reachable": True,
        "ping_latency_ms": 4.2,
        "can_query": not is_exhausted,
        "error": "PoolTimeout" if is_exhausted else None
    }

@app.get("/tools/check-backend-load")
def check_backend_load():
    return {
        "cpu_percent": 24.5 if is_exhausted else 10.2,
        "memory_mb": 195.0,
        "active_http_requests": 14 if is_exhausted else 2
    }

@app.post("/tools/clear-connection-pool")
def clear_connection_pool():
    global is_exhausted
    is_exhausted = False
    return {"status": "success", "message": "Connection pool successfully recycled and drained."}

@app.post("/tools/restart-student-api")
def restart_student_api():
    global is_exhausted
    is_exhausted = False
    return {"status": "success", "message": "Student API gracefully restarted."}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

