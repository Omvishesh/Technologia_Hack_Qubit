"""
Verification Tools — HTTP client wrappers for read-only diagnostic endpoints.

These call Saket's backend to gather evidence for hypothesis verification:
  - check_db_connections: GET /tools/check-db-connections
  - check_db_health:      GET /tools/check-db-health
  - check_backend_load:   GET /tools/check-backend-load

All functions return a ToolResult model.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import get_settings
from ..models import ToolResult


# ─────────────────────────────────────────────────────────────
# Internal HTTP helper
# ─────────────────────────────────────────────────────────────

async def _call_tool_endpoint(path: str, tool_name: str) -> ToolResult:
    """
    Make a GET request to a backend tool endpoint and wrap the
    response in a ToolResult.
    """
    settings = get_settings()
    url = f"{settings.backend_url}{path}"
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            elapsed_ms = (time.monotonic() - start) * 1000

            if response.status_code == 200:
                return ToolResult(
                    tool_name=tool_name,
                    success=True,
                    result=response.json(),
                    latency_ms=round(elapsed_ms, 2),
                )
            else:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    result={"status_code": response.status_code, "body": response.text},
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    latency_ms=round(elapsed_ms, 2),
                )
    except httpx.ConnectError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return ToolResult(
            tool_name=tool_name,
            success=False,
            error=f"Connection error: {exc}",
            latency_ms=round(elapsed_ms, 2),
        )
    except httpx.TimeoutException as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return ToolResult(
            tool_name=tool_name,
            success=False,
            error=f"Timeout: {exc}",
            latency_ms=round(elapsed_ms, 2),
        )
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return ToolResult(
            tool_name=tool_name,
            success=False,
            error=f"Unexpected error: {type(exc).__name__}: {exc}",
            latency_ms=round(elapsed_ms, 2),
        )


# ─────────────────────────────────────────────────────────────
# Public verification tool functions
# ─────────────────────────────────────────────────────────────

async def check_db_connections() -> ToolResult:
    """
    Check the database connection pool status.

    Expected response shape:
    {
        "active_connections": 10,
        "max_pool_size": 10,
        "waiting_requests": 8,
        "pool_exhausted": true
    }
    """
    return await _call_tool_endpoint("/tools/check-db-connections", "check_db_connections")


async def check_db_health() -> ToolResult:
    """
    Check database reachability and query capability.

    Expected response shape:
    {
        "db_reachable": true,
        "ping_latency_ms": 4.2,
        "can_query": false,
        "error": "PoolTimeout"
    }
    """
    return await _call_tool_endpoint("/tools/check-db-health", "check_db_health")


async def check_backend_load() -> ToolResult:
    """
    Check backend service resource utilization.

    Expected response shape:
    {
        "cpu_percent": 18.5,
        "memory_mb": 142.0,
        "active_http_requests": 12
    }
    """
    return await _call_tool_endpoint("/tools/check-backend-load", "check_backend_load")


# ─────────────────────────────────────────────────────────────
# Tool registry — maps tool names to callables
# ─────────────────────────────────────────────────────────────

VERIFICATION_TOOLS: dict[str, Any] = {
    "check_db_connections": check_db_connections,
    "check_db_health": check_db_health,
    "check_backend_load": check_backend_load,
}


async def call_verification_tool(tool_name: str) -> ToolResult:
    """
    Dispatch a verification tool call by name.

    Raises KeyError if the tool name is not registered.
    """
    if tool_name not in VERIFICATION_TOOLS:
        return ToolResult(
            tool_name=tool_name,
            success=False,
            error=f"Unknown verification tool: '{tool_name}'. "
                  f"Available: {list(VERIFICATION_TOOLS.keys())}",
        )
    return await VERIFICATION_TOOLS[tool_name]()
