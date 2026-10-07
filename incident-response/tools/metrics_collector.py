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
                return {
                    "healthy": True,
                    "data": data,
                    "error": None,
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
    return MetricsSnapshot(
        cpu_percent=raw.get("cpu_percent"),
        memory_mb=raw.get("memory_mb"),
        active_http_requests=raw.get("active_http_requests"),
        db_pool_active=raw.get("db_pool_active") or raw.get("active_connections"),
        db_pool_max=raw.get("db_pool_max") or raw.get("max_pool_size"),
        error_rate=raw.get("error_rate"),
        avg_latency_ms=raw.get("avg_latency_ms") or raw.get("latency_ms"),
    )

