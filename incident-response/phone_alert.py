"""
Phone Alert — rings the on-call engineer's phone the moment the approval email goes out.

Uses ntfy (https://ntfy.sh): a free push-notification service with Android and iOS apps.
The engineer subscribes to NTFY_TOPIC in the ntfy app. Approval alerts are sent at max
priority, which can be given an alarm sound and allowed through Do Not Disturb, and they
carry Approve / Reject buttons that open the same links as the email.

Disabled when NTFY_TOPIC is empty. The topic name acts as the password on the public
ntfy.sh server, so keep it unguessable and out of git (it lives in .env).
A failed alert is logged, never raised: the email has already been sent by then.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import get_settings
from .models import Incident

logger = logging.getLogger("incident-response.phone_alert")


def _approval_payload(incident: Incident, topic: str, base_url: str) -> dict[str, Any]:
    rc, rem = incident.root_cause, incident.remediation
    lines = [
        f"Service: {incident.service} · Severity: {incident.severity.value}",
        f"Root cause: {rc.cause} ({rc.confidence:.0%} confidence)" if rc else f"Error: {incident.error_message}",
        f"Proposed fix: {rem.action} · Risk: {rem.risk.value}" if rem else None,
        "Approval email sent — approve or reject below.",
    ]
    link = f"{base_url}/incidents/{incident.id}"
    return {
        "topic": topic,
        "title": f"INCIDENT {incident.id} — approval needed",
        "message": "\n".join(line for line in lines if line),
        "priority": 5,                       # max / urgent: loudest, can bypass Do Not Disturb
        "tags": ["rotating_light"],
        "actions": [
            {"action": "view", "label": "Approve", "url": f"{link}/approve", "clear": True},
            {"action": "view", "label": "Reject", "url": f"{link}/reject", "clear": True},
            {"action": "view", "label": "Timeline", "url": f"{link}/timeline"},
        ],
    }


def _resolved_payload(incident: Incident, topic: str) -> dict[str, Any]:
    details = incident.recovery.details if incident.recovery else "Service restored and verified healthy."
    return {
        "topic": topic,
        "title": f"RESOLVED {incident.id}",
        "message": details,
        "priority": 3,                       # normal: no alarm for good news
        "tags": ["white_check_mark"],
    }


async def send_phone_alert(incident: Incident, kind: str = "approval") -> bool:
    """Push an alert to the engineer's phone. kind: "approval" (urgent) or "resolved"."""
    settings = get_settings()
    if not settings.ntfy_topic:
        return False

    if kind == "approval":
        payload = _approval_payload(incident, settings.ntfy_topic, settings.incident_service_url.rstrip("/"))
    else:
        payload = _resolved_payload(incident, settings.ntfy_topic)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.ntfy_server.rstrip("/"), json=payload)
            resp.raise_for_status()
        logger.info("Phone alert (%s) sent for %s", kind, incident.id)
        return True
    except Exception as exc:
        logger.warning("Phone alert (%s) failed for %s: %s", kind, incident.id, exc)
        return False
