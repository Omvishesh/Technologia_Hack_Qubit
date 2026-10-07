"""
Incident Timeline — Records every pipeline step with timestamps.

Provides utility functions for managing the incident timeline
and formatting it for display/email.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import Incident, TimelineEntry


def add_event(
    incident: Incident,
    stage: str,
    description: str,
    data: dict | None = None,
) -> TimelineEntry:
    """
    Add a timeline event to the incident.

    This is a convenience wrapper around incident.add_timeline_event()
    that also returns the created entry.
    """
    entry = TimelineEntry(
        stage=stage,
        description=description,
        data=data or {},
    )
    incident.timeline.append(entry)
    incident.updated_at = datetime.now(timezone.utc)
    return entry


def format_timeline(incident: Incident) -> str:
    """
    Format the incident timeline as a human-readable string.

    Example output:
        [14:10:05] detection     — Incident detected: DB pool exhausted
        [14:10:06] log_analysis  — Analyzed 42 log entries
        [14:10:07] hypotheses    — Generated 3 hypotheses
        ...
    """
    lines = []
    for entry in incident.timeline:
        ts = entry.timestamp.strftime("%H:%M:%S")
        lines.append(f"[{ts}] {entry.stage:<20} — {entry.description}")
    return "\n".join(lines)


def get_duration_seconds(incident: Incident) -> float | None:
    """
    Calculate the total incident duration from first to last timeline entry.

    Returns None if the timeline has fewer than 2 entries.
    """
    if len(incident.timeline) < 2:
        return None
    first = incident.timeline[0].timestamp
    last = incident.timeline[-1].timestamp
    return (last - first).total_seconds()

