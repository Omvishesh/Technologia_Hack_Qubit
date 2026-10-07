"""
Remediation Tools — HTTP client wrappers for allowlisted remediation endpoints.

These call Saket's backend to execute approved remediation actions:
  - clear_connection_pool: POST /tools/clear-connection-pool
  - restart_student_api:   POST /tools/restart-student-api

All functions return a ToolResult model.

IMPORTANT: These tools should ONLY be called after:
  1. Safety check passes
  2. DevOps engineer approves via email
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import get_settings
from ..models import ToolResult


# ─────────────────────────────────────────────────────────────
# Allowlist — only these actions can ever be executed
# ─────────────────────────────────────────────────────────────

ALLOWED_REMEDIATION_ACTIONS: set[str] = {
    "clear_connection_pool",
    "restart_student_api",
}


# ─────────────────────────────────────────────────────────────
# Internal HTTP helper
# ─────────────────────────────────────────────────────────────

async def _call_remediation_endpoint(path: str, tool_name: str) -> ToolResult:
    """
    Make a POST request to a backend remediation endpoint and wrap
    the response in a ToolResult.
    """
    settings = get_settings()
    url = f"{settings.backend_url}{path}"
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url)
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
# Public remediation tool functions
# ─────────────────────────────────────────────────────────────

async def clear_connection_pool() -> ToolResult:
    """
    Drop all held connections and recycle the PostgreSQL connection pool.

    This restores availability when connections are exhausted or stale.
    """
    return await _call_remediation_endpoint(
        "/tools/clear-connection-pool", "clear_connection_pool"
    )


async def restart_student_api() -> ToolResult:
    """
    Gracefully restart the Student Query API service process.

    This is the general-purpose remediation for most backend failures.
    """
    return await _call_remediation_endpoint(
        "/tools/restart-student-api", "restart_student_api"
    )


# ─────────────────────────────────────────────────────────────
# Tool registry — maps tool names to callables
# ─────────────────────────────────────────────────────────────

REMEDIATION_TOOLS: dict[str, Any] = {
    "clear_connection_pool": clear_connection_pool,
    "restart_student_api": restart_student_api,
}


def is_action_allowed(tool_name: str) -> bool:
    """Check if a remediation action is in the allowlist."""
    return tool_name in ALLOWED_REMEDIATION_ACTIONS


async def call_remediation_tool(tool_name: str) -> ToolResult:
    """
    Dispatch a remediation tool call by name.

    Enforces the allowlist — rejects any action not explicitly permitted.
    """
    if not is_action_allowed(tool_name):
        return ToolResult(
            tool_name=tool_name,
            success=False,
            error=f"BLOCKED: '{tool_name}' is NOT in the allowed remediation actions. "
                  f"Allowed: {ALLOWED_REMEDIATION_ACTIONS}",
        )
    return await REMEDIATION_TOOLS[tool_name]()

