"""
Metrics Collector — Fetches runtime metrics from the backend.

Calls GET /metrics and GET /health on Saket's backend API to gather
real-time system state for incident detection and verification.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import get_settings
from ..models import MetricsSnapshot


async def collect_metrics() -> dict[str, Any]:
    """
    Fetch current metrics from the backend /metrics endpoint.

    Returns:
        Dict with keys:
        - "success": bool
        - "metrics": dict — raw metrics data
        - "error": str | None
        - "latency_ms": float
    """
    settings = get_settings()
    url = f"{settings.backend_url}/metrics"
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            elapsed_ms = (time.monotonic() - start) * 1000

            if response.status_code == 200:
                return {
                    "success": True,
                    "metrics": response.json(),
                    "error": None,
                    "latency_ms": round(elapsed_ms, 2),
                }
            else:
                return {
                    "success": False,
                    "metrics": {},
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "latency_ms": round(elapsed_ms, 2),
                }

    except httpx.ConnectError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "success": False,
            "metrics": {},
            "error": f"Connection error: {exc}",
            "latency_ms": round(elapsed_ms, 2),
        }
    except httpx.TimeoutException as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "success": False,
            "metrics": {},
            "error": f"Timeout: {exc}",
            "latency_ms": round(elapsed_ms, 2),
        }
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "success": False,
            "metrics": {},
            "error": f"Unexpected error: {type(exc).__name__}: {exc}",
            "latency_ms": round(elapsed_ms, 2),
        }


async def check_health() -> dict[str, Any]:
    """
    Check backend service health via GET /health.

    Returns:
        Dict with keys:
        - "healthy": bool
        - "data": dict — full health response
        - "error": str | None
        - "latency_ms": float
    """
    settings = get_settings()
    url = f"{settings.backend_url}/health"
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            elapsed_ms = (time.monotonic() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                # student-api answers 200 even when degraded (e.g. pool exhausted),
                # so trust the body's verdict when it gives one.
                healthy = data.get("healthy", data.get("status", "healthy") in ("healthy", "ok"))
                error = None
                if not healthy:
                    error = (
                        data.get("error")
                        or (data.get("database") or {}).get("error")
                        or f"Backend status: {data.get('status')}"
                    )
                return {
                    "healthy": healthy,
                    "data": data,
                    "error": error,
                    "latency_ms": round(elapsed_ms, 2),
                }
            else:
                return {
                    "healthy": False,
                    "data": {},
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "latency_ms": round(elapsed_ms, 2),
                }

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "healthy": False,
            "data": {},
            "error": f"Backend unreachable: {exc}",
            "latency_ms": round(elapsed_ms, 2),
        }
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "healthy": False,
            "data": {},
            "error": f"Unexpected error: {type(exc).__name__}: {exc}",
            "latency_ms": round(elapsed_ms, 2),
        }


def parse_metrics_snapshot(raw: dict[str, Any]) -> MetricsSnapshot:
    """
    Parse raw metrics dict into a typed MetricsSnapshot model.

    Handles varying key names from the backend gracefully.
    """
    def first(*keys: str) -> Any:
        # First non-None value — 0 is a valid reading, so don't use `or`.
        return next((raw[k] for k in keys if raw.get(k) is not None), None)

    error_rate = raw.get("error_rate")
    if error_rate is None and raw.get("error_rate_percent") is not None:
        error_rate = raw["error_rate_percent"] / 100  # student-api reports a percentage

    return MetricsSnapshot(
        cpu_percent=raw.get("cpu_percent"),
        memory_mb=raw.get("memory_mb"),
        active_http_requests=raw.get("active_http_requests"),
        db_pool_active=first("db_pool_active", "active_connections", "active_db_connections"),
        db_pool_max=first("db_pool_max", "max_pool_size", "max_db_connections"),
        error_rate=error_rate,
        avg_latency_ms=first("avg_latency_ms", "latency_ms"),
    )

