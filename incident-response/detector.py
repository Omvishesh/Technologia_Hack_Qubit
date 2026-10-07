"""
Incident Detector — Polls backend health/metrics and triggers incidents.

Runs on a configurable interval (DETECTOR_INTERVAL_SECONDS). When it detects
an anomaly (error rate above threshold, health check failure, etc.), it creates
an Incident and returns it for the pipeline orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from .config import get_settings
from .models import Incident, IncidentStatus, Severity, MetricsSnapshot
from .incident_manager import get_open_incident
from .log_monitor import classify
from .tools.metrics_collector import check_health, collect_metrics, parse_metrics_snapshot

logger = logging.getLogger("incident-response.detector")


class IncidentDetector:
    """
    Monitors the backend for failures and creates Incidents.

    Usage:
        detector = IncidentDetector(on_incident=my_callback)
        await detector.start()  # runs forever
        # or
        incident = await detector.check_once()  # single poll
    """

    def __init__(
        self,
        on_incident: Callable[[Incident], Awaitable[None]] | None = None,
    ):
        self._settings = get_settings()
        self._on_incident = on_incident
        self._running = False
        self._consecutive_failures = 0
        self._last_healthy = True

    async def check_once(self) -> Incident | None:
        """
        Perform a single health/metrics check.

        Returns an Incident only on the healthy -> unhealthy transition, else None.
        """
        # 1. Check health endpoint
        health = await check_health()

        # 2. Check metrics endpoint
        metrics_raw = await collect_metrics()

        # 3. Evaluate for incidents
        incident = self._evaluate(health, metrics_raw)

        if incident:
            self._consecutive_failures += 1
            is_new_outage = self._last_healthy
            self._last_healthy = False
            logger.warning(
                "Incident detected: %s (consecutive failures: %d)",
                incident.error_message,
                self._consecutive_failures,
            )
            if not is_new_outage or get_open_incident():
                # Same outage that already raised an incident (here or via the log
                # monitor) — don't re-run the pipeline / re-send the approval email.
                return None
        else:
            if not self._last_healthy:
                logger.info("Backend recovered — health checks passing again")
            self._consecutive_failures = 0
            self._last_healthy = True

        return incident

    async def start(self) -> None:
        """Start the polling loop. Runs until stop() is called."""
        self._running = True
        interval = self._settings.detector_interval_seconds
        logger.info("Incident detector started (interval=%ds)", interval)

        while self._running:
            try:
                incident = await self.check_once()
                if incident and self._on_incident:
                    await self._on_incident(incident)
            except Exception as exc:
                logger.error("Detector loop error: %s", exc, exc_info=True)

            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
        logger.info("Incident detector stopped")

    def _evaluate(
        self,
        health: dict[str, Any],
        metrics_raw: dict[str, Any],
    ) -> Incident | None:
        """
        Analyze health and metrics data to determine if an incident
        should be created.
        """
        # ── Health check failure ─────────────────────────────
        if not health.get("healthy", False):
            error_msg = health.get("error", "Health check failed")
            incident = Incident(
                # Same error-catalogue classification the log monitor uses
                error_code=classify({"status": 500, "error": error_msg}),
                error_message=error_msg,
                severity=Severity.HIGH,
                status=IncidentStatus.DETECTED,
            )
            incident.add_timeline_event(
                stage="detection",
                description=f"Health check failed: {error_msg}",
                data={"health_response": health},
            )

            # Attach metrics if available
            if metrics_raw.get("success"):
                incident.metrics = parse_metrics_snapshot(metrics_raw["metrics"])

            return incident

        # ── Metrics-based detection ──────────────────────────
        if metrics_raw.get("success"):
            metrics = metrics_raw["metrics"]
            snapshot = parse_metrics_snapshot(metrics)

            # Check error rate threshold
            error_rate = snapshot.error_rate
            if error_rate is not None and error_rate > self._settings.error_rate_threshold:
                incident = Incident(
                    error_code="HIGH_ERROR_RATE",
                    error_message=f"Error rate {error_rate:.1%} exceeds threshold {self._settings.error_rate_threshold:.1%}",
                    severity=Severity.HIGH,
                    status=IncidentStatus.DETECTED,
                    metrics=snapshot,
                )
                incident.add_timeline_event(
                    stage="detection",
                    description=f"High error rate detected: {error_rate:.1%}",
                    data={"metrics": metrics},
                )
                return incident

            # Check connection pool exhaustion
            if (
                snapshot.db_pool_active is not None
                and snapshot.db_pool_max is not None
                and snapshot.db_pool_active >= snapshot.db_pool_max
            ):
                incident = Incident(
                    error_code="DB_CONNECTION_EXHAUSTION",
                    error_message=f"DB pool exhausted: {snapshot.db_pool_active}/{snapshot.db_pool_max} connections active",
                    severity=Severity.HIGH,
                    status=IncidentStatus.DETECTED,
                    metrics=snapshot,
                )
                incident.add_timeline_event(
                    stage="detection",
                    description="Database connection pool exhaustion detected",
                    data={"metrics": metrics},
                )
                return incident

            # Check high CPU
            if snapshot.cpu_percent is not None and snapshot.cpu_percent > 80:
                incident = Incident(
                    error_code="HIGH_CPU",
                    error_message=f"CPU usage critically high: {snapshot.cpu_percent:.1f}%",
                    severity=Severity.MEDIUM,
                    status=IncidentStatus.DETECTED,
                    metrics=snapshot,
                )
                incident.add_timeline_event(
                    stage="detection",
                    description=f"High CPU detected: {snapshot.cpu_percent:.1f}%",
                    data={"metrics": metrics},
                )
                return incident

        # Nothing abnormal
        return None

