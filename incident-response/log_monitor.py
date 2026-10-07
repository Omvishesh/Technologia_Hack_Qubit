"""
Log Monitor Agent — continuously tails the student-api's structured JSON log
(backend/logs/app.log, one line per /chat request) and raises an incident as
soon as failures appear, instead of waiting for /health to degrade.

Why: /health only notices DB-level outages, and the backend's error rate is
cumulative since startup. The log shows every failed or slow request as it
happens, with its exact error — so detection is faster and the incident starts
with the right error-catalogue code and the offending request IDs.

Source: LOG_FILE_PATH when readable from this machine; otherwise polls the
backend's GET /logs (e.g. when the services run on different hosts).

Rules (within LOG_WINDOW_SECONDS):
  - a known infrastructure failure (pool exhausted, DB unreachable) → raise immediately
  - other 5xx errors or requests slower than LOG_SLOW_REQUEST_MS → raise at LOG_ERROR_THRESHOLD
One outage → one incident: nothing is raised while another incident is open, and
log lines from before the last incident closed are never counted again.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from .config import PROJECT_ROOT, get_settings
from .incident_manager import get_open_incident, last_closed_at, store_incident
from .models import Incident, IncidentStatus, Severity

logger = logging.getLogger("incident-response.log_monitor")

# (error-catalogue code, pattern in the logged error text), most specific first
_SIGNATURES: list[tuple[str, re.Pattern[str]]] = [
    ("DB_CONNECTION_EXHAUSTION", re.compile(r"pool ?timeout|pool exhausted|queuepool limit|too many (clients|connections)", re.I)),
    ("DB_UNAVAILABLE", re.compile(r"connection refused|host unreachable|could not connect|connectionerror|server closed the connection", re.I)),
    ("DB_QUERY_TIMEOUT", re.compile(r"statement timeout|canceling statement|querycanceled", re.I)),
    ("INVALID_SQL", re.compile(r"syntax error|undefinedtable|undefinedcolumn|no such (table|column)|does not exist|programmingerror|unsafe sql", re.I)),
]
# Unambiguous infrastructure failures: one is enough
_IMMEDIATE = {"DB_CONNECTION_EXHAUSTION", "DB_UNAVAILABLE"}


def classify(event: dict[str, Any]) -> str:
    """Map one log event to an error-catalogue code."""
    if (event.get("status") or 0) >= 500:
        text = str(event.get("error") or "")
        for code, pattern in _SIGNATURES:
            if pattern.search(text):
                return code
        return "SERVICE_UNAVAILABLE"
    return "API_TIMEOUT"  # not an error status, so it was flagged as slow


class LogMonitor:
    """Tails the backend log and calls `on_incident` when a failure pattern appears."""

    def __init__(self, on_incident: Callable[[Incident], Awaitable[Any]] | None = None):
        self._settings = get_settings()
        self._on_incident = on_incident
        path = Path(self._settings.log_file_path)
        self._path = path if path.is_absolute() else PROJECT_ROOT / path
        self._offset: int | None = None           # file read position (None = start at end)
        self._http_last_ts: str | None = None     # newest timestamp seen via GET /logs
        self._window: deque[tuple[datetime, dict[str, Any]]] = deque()  # (ingested_at, event)
        self._running = False
        self._tasks: set[asyncio.Task] = set()   # running pipelines (kept referenced until done)
        self.source = "not started"
        self.lines_read = 0
        self.incidents_raised = 0
        self.last_event_at: datetime | None = None

    # ── Reading ──────────────────────────────────────────────

    def _read_file(self) -> list[dict[str, Any]]:
        size = self._path.stat().st_size
        if self._offset is None or size < self._offset:  # first read, or file truncated/rotated
            self._offset = size if self._offset is None else 0
        if size == self._offset:
            return []
        with open(self._path, "rb") as f:
            f.seek(self._offset)
            chunk = f.read(size - self._offset)
        end = chunk.rfind(b"\n")
        if end == -1:
            return []  # partial line still being written
        self._offset += end + 1
        events = []
        for raw in chunk[:end].splitlines():
            try:
                events.append(json.loads(raw))
            except ValueError:
                continue
        return events

    async def _read_http(self) -> list[dict[str, Any]]:
        url = f"{self._settings.backend_url.rstrip('/')}/logs"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params={"limit": 200})
            resp.raise_for_status()
            data = resp.json()
        logs = data if isinstance(data, list) else data.get("logs", [])
        if self._http_last_ts is None:  # first poll: skip history, like the file tail
            self._http_last_ts = max((e.get("timestamp", "") for e in logs), default="")
            return []
        new = [e for e in logs if e.get("timestamp", "") > self._http_last_ts]
        if new:
            self._http_last_ts = max(e.get("timestamp", "") for e in new)
        return new

    async def _read_new_events(self) -> list[dict[str, Any]]:
        if self._path.exists():
            self.source = f"file {self._path}"
            return self._read_file()
        self.source = f"HTTP {self._settings.backend_url.rstrip('/')}/logs (log file not found)"
        return await self._read_http()

    # ── Detection ────────────────────────────────────────────

    def _is_bad(self, event: dict[str, Any]) -> bool:
        return (event.get("status") or 0) >= 500 or (event.get("latency_ms") or 0) >= self._settings.log_slow_request_ms

    def evaluate(self) -> Incident | None:
        """Check the sliding window; return a new Incident if one should be raised."""
        now = datetime.now(timezone.utc)
        horizon = now - timedelta(seconds=self._settings.log_window_seconds)
        while self._window and self._window[0][0] < horizon:
            self._window.popleft()

        if get_open_incident():
            self._window.clear()  # this outage is already being handled
            return None

        closed = last_closed_at()
        bad = [e for seen, e in self._window if self._is_bad(e) and (closed is None or seen > closed)]
        if not bad:
            return None

        code = classify(bad[-1])
        needed = 1 if code in _IMMEDIATE else self._settings.log_error_threshold
        if len(bad) < needed:
            return None

        self._window.clear()
        latest = bad[-1]
        errors = sum(1 for e in bad if (e.get("status") or 0) >= 500)
        what = f"{errors} failed" if errors else f"{len(bad)} slow"
        detail = latest.get("error") or f"latency {latest.get('latency_ms')} ms"
        incident = Incident(
            error_code=code,
            error_message=f"{what} {latest.get('endpoint', 'API')} request(s) in the last "
                          f"{self._settings.log_window_seconds}s — {detail}",
            request_id=latest.get("request_id"),
            severity=Severity.HIGH,
            status=IncidentStatus.DETECTED,
            raw_logs=bad[-20:],
        )
        incident.add_timeline_event(
            stage="detection",
            description=f"Log monitor: {what} request(s) in the backend log, classified as {code}",
            data={"source": "log_monitor", "request_ids": [e.get("request_id") for e in bad[-10:]]},
        )
        return incident

    # ── Loop ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Run until stop() is called."""
        self._running = True
        logger.info("Log monitor started (log file: %s)", self._path)
        while self._running:
            try:
                events = await self._read_new_events()
                if events:
                    now = datetime.now(timezone.utc)
                    self._window.extend((now, e) for e in events)
                    self.lines_read += len(events)
                    self.last_event_at = now

                incident = self.evaluate()
                if incident:
                    self.incidents_raised += 1
                    logger.warning("Log monitor raised %s: %s", incident.id, incident.error_message)
                    store_incident(incident)  # visible as "open" right away, so other detectors stand down
                    if self._on_incident:
                        task = asyncio.create_task(self._on_incident(incident))
                        self._tasks.add(task)
                        task.add_done_callback(self._pipeline_done)
            except Exception as exc:
                logger.error("Log monitor error: %s", exc)
            await asyncio.sleep(self._settings.log_monitor_interval_seconds)

    def _pipeline_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.error("Pipeline for a log-monitor incident failed: %s", task.exception())

    def stop(self) -> None:
        self._running = False
        logger.info("Log monitor stopped")

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "source": self.source,
            "lines_read": self.lines_read,
            "events_in_window": len(self._window),
            "window_seconds": self._settings.log_window_seconds,
            "incidents_raised": self.incidents_raised,
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
        }
