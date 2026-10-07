"""
Data models for the Incident Response System.

All inter-agent communication uses these Pydantic models to ensure
type safety, serialization, and clear contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    ANALYZING = "analyzing"
    HYPOTHESES_GENERATED = "hypotheses_generated"
    VERIFYING = "verifying"
    ROOT_CAUSE_CONFIRMED = "root_cause_confirmed"
    REMEDIATION_PROPOSED = "remediation_proposed"
    SAFETY_CHECKED = "safety_checked"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    RECOVERY_FAILED = "recovery_failed"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ─────────────────────────────────────────────────────────────
# Helper: ID generators
# ─────────────────────────────────────────────────────────────

def _incident_id() -> str:
    return f"INC-{uuid.uuid4().hex[:8].upper()}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────
# Timeline
# ─────────────────────────────────────────────────────────────

class TimelineEntry(BaseModel):
    """A single event in the incident timeline."""
    timestamp: datetime = Field(default_factory=_now)
    stage: str                          # e.g. "detection", "log_analysis", "hypothesis"
    description: str
    data: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# Log Analysis
# ─────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    """A single structured log line from the backend."""
    timestamp: Optional[str] = None
    service: Optional[str] = None
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    user_query: Optional[str] = None
    generated_sql: Optional[str] = None
    db_pool_active: Optional[int] = None
    db_pool_max: Optional[int] = None
    status: Optional[int] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    # Allow arbitrary extra fields from the backend
    extra: dict[str, Any] = Field(default_factory=dict)


class LogSummary(BaseModel):
    """Output of the Log Analysis Agent."""
    summary: str                        # Human-readable summary
    error_signals: list[str]            # Key error indicators extracted
    error_count: int = 0
    avg_latency_ms: Optional[float] = None
    dominant_error: Optional[str] = None
    time_range: Optional[str] = None    # e.g. "14:10 - 14:15 UTC"
    raw_log_count: int = 0


# ─────────────────────────────────────────────────────────────
# Hypothesis
# ─────────────────────────────────────────────────────────────

class Hypothesis(BaseModel):
    """A single root-cause hypothesis with confidence and verification plan."""
    rank: int                           # 1, 2, or 3
    title: str                          # e.g. "Database connection pool exhaustion"
    description: str                    # Detailed explanation
    confidence: float                   # 0.0 – 1.0
    verification_tool: str              # Tool name to call, e.g. "check_db_connections"
    expected_if_true: str               # What the tool result should show if this is correct


# ─────────────────────────────────────────────────────────────
# Verification Tool Results
# ─────────────────────────────────────────────────────────────

class ToolResult(BaseModel):
    """Result from calling a single verification/remediation tool."""
    tool_name: str
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=_now)
    latency_ms: Optional[float] = None


# ─────────────────────────────────────────────────────────────
# Root Cause Analysis
# ─────────────────────────────────────────────────────────────

class RootCause(BaseModel):
    """Confirmed root cause from the RCA Agent."""
    cause: str                          # e.g. "Database connection pool exhausted"
    evidence: list[str]                 # Evidence items from tool results
    confidence: float                   # 0.0 – 1.0
    confirmed_hypothesis_rank: int      # Which hypothesis was confirmed (1-3)
    supporting_data: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# Remediation
# ─────────────────────────────────────────────────────────────

class Remediation(BaseModel):
    """Proposed remediation action from the Remediation Agent."""
    action: str                         # Human-readable action, e.g. "Restart Student Query API"
    tool_name: str                      # Allowlisted tool to call, e.g. "restart_student_api"
    reason: str                         # Why this action is appropriate
    risk: RiskLevel = RiskLevel.LOW
    blast_radius: str                   # e.g. "Student Query API only"
    requires_approval: bool = True
    estimated_recovery_seconds: int = 30


# ─────────────────────────────────────────────────────────────
# Safety Check
# ─────────────────────────────────────────────────────────────

class SafetyCheck(BaseModel):
    """Result of the Safety / Permission Layer evaluation."""
    allowed: bool
    action: str
    target_service: str
    is_action_allowlisted: bool
    is_blast_radius_acceptable: bool
    requires_human_approval: bool
    rejection_reason: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Metrics Snapshot
# ─────────────────────────────────────────────────────────────

class MetricsSnapshot(BaseModel):
    """A point-in-time snapshot of backend metrics."""
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    active_http_requests: Optional[int] = None
    db_pool_active: Optional[int] = None
    db_pool_max: Optional[int] = None
    error_rate: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    timestamp: datetime = Field(default_factory=_now)


# ─────────────────────────────────────────────────────────────
# Recovery Verification
# ─────────────────────────────────────────────────────────────

class RecoveryResult(BaseModel):
    """Outcome of post-remediation recovery verification."""
    recovered: bool
    health_check_passed: bool
    error_rate_before: Optional[float] = None
    error_rate_after: Optional[float] = None
    latency_before_ms: Optional[float] = None
    latency_after_ms: Optional[float] = None
    db_connected: bool = False
    details: str = ""


# ─────────────────────────────────────────────────────────────
# Incident (top-level aggregate)
# ─────────────────────────────────────────────────────────────

class Incident(BaseModel):
    """
    The central data object for an incident.
    Accumulates data as it flows through the pipeline stages.
    """
    id: str = Field(default_factory=_incident_id)
    service: str = "student-api"
    severity: Severity = Severity.HIGH
    status: IncidentStatus = IncidentStatus.DETECTED

    # Detection context
    error_code: Optional[str] = None        # e.g. "DB_CONNECTION_TIMEOUT"
    error_message: Optional[str] = None
    request_id: Optional[str] = None

    # Pipeline outputs (populated as agents run)
    raw_logs: list[dict[str, Any]] = Field(default_factory=list)
    metrics: Optional[MetricsSnapshot] = None
    log_summary: Optional[LogSummary] = None
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    verification_results: list[ToolResult] = Field(default_factory=list)
    root_cause: Optional[RootCause] = None
    remediation: Optional[Remediation] = None
    safety_check: Optional[SafetyCheck] = None
    recovery: Optional[RecoveryResult] = None

    # Approval tracking
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # Timeline
    timeline: list[TimelineEntry] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    resolved_at: Optional[datetime] = None

    def add_timeline_event(self, stage: str, description: str, data: dict[str, Any] | None = None) -> None:
        """Append a new entry to the incident timeline."""
        self.timeline.append(
            TimelineEntry(stage=stage, description=description, data=data or {})
        )
        self.updated_at = _now()


# ─────────────────────────────────────────────────────────────
# Incident Report (for email)
# ─────────────────────────────────────────────────────────────

class IncidentReport(BaseModel):
    """
    Flattened view of the incident for rendering into the approval email.
    Contains all information the DevOps engineer needs to make a decision.
    """
    incident_id: str
    service: str
    severity: Severity
    what_happened: str
    log_summary: str
    hypotheses: list[dict[str, Any]]
    verification_results: list[dict[str, Any]]
    root_cause: str
    root_cause_confidence: float
    evidence: list[str]
    proposed_action: str
    remediation_tool: str
    risk: RiskLevel
    blast_radius: str
    timestamp: str

    @classmethod
    def from_incident(cls, incident: Incident) -> IncidentReport:
        """Build a report from a fully-analyzed Incident."""
        return cls(
            incident_id=incident.id,
            service=incident.service,
            severity=incident.severity,
            what_happened=incident.error_message or "Unknown error",
            log_summary=incident.log_summary.summary if incident.log_summary else "",
            hypotheses=[
                {
                    "rank": h.rank,
                    "title": h.title,
                    "confidence": f"{h.confidence:.0%}",
                }
                for h in incident.hypotheses
            ],
            verification_results=[
                {
                    "tool": tr.tool_name,
                    "success": tr.success,
                    "result": tr.result,
                }
                for tr in incident.verification_results
            ],
            root_cause=incident.root_cause.cause if incident.root_cause else "",
            root_cause_confidence=incident.root_cause.confidence if incident.root_cause else 0.0,
            evidence=incident.root_cause.evidence if incident.root_cause else [],
            proposed_action=incident.remediation.action if incident.remediation else "",
            remediation_tool=incident.remediation.tool_name if incident.remediation else "",
            risk=incident.remediation.risk if incident.remediation else RiskLevel.LOW,
            blast_radius=incident.remediation.blast_radius if incident.remediation else "",
            timestamp=incident.created_at.isoformat(),
        )

