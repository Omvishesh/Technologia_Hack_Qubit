"""
Log Collector — Fetches structured logs from the backend.

Calls GET /logs on Saket's backend API to retrieve recent application
log entries for analysis by the Log Analysis Agent.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import get_settings


async def collect_logs(
    limit: int = 100,
    level: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """
    Fetch recent structured logs from the backend.

    Args:
        limit:  Maximum number of log entries to return.
        level:  Optional filter by log level (e.g. "ERROR").
        since:  Optional ISO timestamp to fetch logs after.

    Returns:
        Dict with keys:
        - "success": bool
        - "logs": list[dict] — raw log entries
        - "count": int — number of entries returned
        - "error": str | None — error message if failed
        - "latency_ms": float
    """
    settings = get_settings()
    url = f"{settings.backend_url}/logs"
    params: dict[str, Any] = {"limit": limit}
    if level:
        params["level"] = level
    if since:
        params["since"] = since

    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            elapsed_ms = (time.monotonic() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                # The backend may return logs as a list or wrapped in an object
                logs = data if isinstance(data, list) else data.get("logs", [])
                return {
                    "success": True,
                    "logs": logs,
                    "count": len(logs),
                    "error": None,
                    "latency_ms": round(elapsed_ms, 2),
                }
            else:
                return {
                    "success": False,
                    "logs": [],
                    "count": 0,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "latency_ms": round(elapsed_ms, 2),
                }

    except httpx.ConnectError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "success": False,
            "logs": [],
            "count": 0,
            "error": f"Connection error (backend unreachable): {exc}",
            "latency_ms": round(elapsed_ms, 2),
        }
    except httpx.TimeoutException as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "success": False,
            "logs": [],
            "count": 0,
            "error": f"Timeout fetching logs: {exc}",
            "latency_ms": round(elapsed_ms, 2),
        }
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "success": False,
            "logs": [],
            "count": 0,
            "error": f"Unexpected error: {type(exc).__name__}: {exc}",
            "latency_ms": round(elapsed_ms, 2),
        }


async def collect_error_logs(limit: int = 50) -> dict[str, Any]:
    """Convenience: fetch only ERROR-level logs."""
    return await collect_logs(limit=limit, level="ERROR")
