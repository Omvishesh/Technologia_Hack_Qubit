"""
Recovery Verification — Post-remediation health checks.

After an approved remediation tool executes, this module verifies
that the service actually recovered.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .config import get_settings
from .models import RecoveryResult
from .tools.metrics_collector import check_health, collect_metrics, parse_metrics_snapshot

logger = logging.getLogger("incident-response.recovery")


async def verify_recovery(
    wait_seconds: int = 10,
    max_retries: int = 3,
    retry_delay: int = 5,
    pre_metrics: dict[str, Any] | None = None,
) -> RecoveryResult:
    """
    Verify that the backend has recovered after remediation.

    Steps:
    1. Wait for the service to restart/stabilize
    2. Check /health
    3. Check /metrics for error rate and latency
    4. Compare before/after if pre_metrics provided

    Args:
        wait_seconds: Initial wait before checking.
        max_retries: Number of health check retry attempts.
        retry_delay: Seconds between retries.
        pre_metrics: Metrics snapshot from before remediation for comparison.

    Returns:
        RecoveryResult with before/after comparison.
    """
    logger.info("Waiting %ds for service recovery...", wait_seconds)
    await asyncio.sleep(wait_seconds)

    # Retry loop for health check
    health_passed = False
    last_health: dict[str, Any] = {}

    for attempt in range(1, max_retries + 1):
        logger.info("Recovery check attempt %d/%d", attempt, max_retries)

        last_health = await check_health()
        if last_health.get("healthy"):
            health_passed = True
            logger.info("Health check PASSED on attempt %d", attempt)
            break
        else:
            logger.warning(
                "Health check failed (attempt %d): %s",
                attempt,
                last_health.get("error"),
            )
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

    # Collect post-remediation metrics
    post_metrics_raw = await collect_metrics()
    post_snapshot = None
    if post_metrics_raw.get("success"):
        post_snapshot = parse_metrics_snapshot(post_metrics_raw["metrics"])

    # Build recovery result
    error_rate_after = post_snapshot.error_rate if post_snapshot else None
    latency_after = post_snapshot.avg_latency_ms if post_snapshot else None
    db_connected = last_health.get("data", {}).get("db_connected", health_passed)

    # Before values from pre-metrics
    error_rate_before = None
    latency_before = None
    if pre_metrics:
        error_rate_before = pre_metrics.get("error_rate")
        latency_before = pre_metrics.get("avg_latency_ms") or pre_metrics.get("latency_ms")

    # Determine overall recovery
    recovered = health_passed

    # Build details string
    details_parts = []
    if health_passed:
        details_parts.append("Health check: PASSED")
    else:
        details_parts.append(f"Health check: FAILED ({last_health.get('error', 'unknown')})")

    if error_rate_before is not None and error_rate_after is not None:
        details_parts.append(
            f"Error rate: {error_rate_before:.1%} → {error_rate_after:.1%}"
        )
    if latency_before is not None and latency_after is not None:
        details_parts.append(
            f"Latency: {latency_before:.0f}ms → {latency_after:.0f}ms"
        )

    result = RecoveryResult(
        recovered=recovered,
        health_check_passed=health_passed,
        error_rate_before=error_rate_before,
        error_rate_after=error_rate_after,
        latency_before_ms=latency_before,
        latency_after_ms=latency_after,
        db_connected=db_connected,
        details=" | ".join(details_parts),
    )

    if recovered:
        logger.info("Recovery VERIFIED: %s", result.details)
    else:
        logger.warning("Recovery FAILED: %s", result.details)

    return result

