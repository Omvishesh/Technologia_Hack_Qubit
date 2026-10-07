"""
Error Catalogue for the Incident Response System.

Defines every known failure type with its symptoms, relevant log signals,
verification tool, expected tool result, remediation action, risk, and blast radius.

The LLM agents reference this catalogue to map observed errors to structured
hypotheses and remediations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ErrorDefinition:
    """A single entry in the error catalogue."""
    name: str
    error_code: str
    symptoms: list[str]
    relevant_log_signals: list[str]
    verification_tool: str
    expected_tool_result: dict[str, object]
    remediation_tool: str
    remediation_description: str
    risk: str           # LOW | MEDIUM | HIGH
    blast_radius: str


# ─────────────────────────────────────────────────────────────
# The Catalogue
# ─────────────────────────────────────────────────────────────

ERROR_CATALOGUE: list[ErrorDefinition] = [

    # 1 ── Database Connection Exhaustion ─────────────────────
    ErrorDefinition(
        name="Database Connection Exhaustion",
        error_code="DB_CONNECTION_EXHAUSTION",
        symptoms=[
            "Requests failing with pool timeout errors",
            "db_pool_active equals db_pool_max in logs",
            "Increasing request latency before failures",
            "HTTP 500 responses on /chat endpoint",
        ],
        relevant_log_signals=[
            "asyncpg.exceptions.PoolTimeoutError",
            "Timeout waiting for connection from pool",
            "connection pool exhausted",
            "db_pool_active == db_pool_max",
        ],
        verification_tool="check_db_connections",
        expected_tool_result={
            "pool_exhausted": True,
            "active_connections_at_max": True,
            "waiting_requests_gt_zero": True,
        },
        remediation_tool="clear_connection_pool",
        remediation_description="Clear and recycle the database connection pool to release stale/leaked connections",
        risk="LOW",
        blast_radius="Student Query API only — brief reconnection delay",
    ),

    # 2 ── Database Unavailable ───────────────────────────────
    ErrorDefinition(
        name="Database Unavailable",
        error_code="DB_UNAVAILABLE",
        symptoms=[
            "All database queries fail immediately",
            "Connection refused errors in logs",
            "Health check reports db_reachable=false",
            "HTTP 500 on all /chat requests",
        ],
        relevant_log_signals=[
            "connection refused",
            "could not connect to server",
            "ConnectionRefusedError",
            "db_reachable: false",
        ],
        verification_tool="check_db_health",
        expected_tool_result={
            "db_reachable": False,
            "can_query": False,
        },
        remediation_tool="restart_student_api",
        remediation_description="Restart the Student Query API service (which will re-establish DB connection)",
        risk="LOW",
        blast_radius="Student Query API only",
    ),

    # 3 ── Database Query Timeout ─────────────────────────────
    ErrorDefinition(
        name="Database Query Timeout",
        error_code="DB_QUERY_TIMEOUT",
        symptoms=[
            "Queries taking abnormally long (>3000ms)",
            "Timeout errors on specific queries",
            "Elevated average latency in metrics",
            "Some requests succeed while others timeout",
        ],
        relevant_log_signals=[
            "QueryCanceledError",
            "canceling statement due to statement timeout",
            "latency_ms > 3000",
            "query timeout",
        ],
        verification_tool="check_db_health",
        expected_tool_result={
            "db_reachable": True,
            "can_query": False,
            "high_ping_latency": True,
        },
        remediation_tool="clear_connection_pool",
        remediation_description="Clear connection pool to drop any stuck/slow queries and reset state",
        risk="LOW",
        blast_radius="Student Query API only — in-flight queries will be cancelled",
    ),

    # 4 ── Backend API Timeout ────────────────────────────────
    ErrorDefinition(
        name="Backend API Timeout",
        error_code="API_TIMEOUT",
        symptoms=[
            "Frontend receives timeout or no response",
            "Backend requests exceeding 5-10 second threshold",
            "Gateway timeout errors",
            "High latency across all endpoints",
        ],
        relevant_log_signals=[
            "request timeout",
            "latency_ms > 5000",
            "ReadTimeout",
            "504 Gateway Timeout",
        ],
        verification_tool="check_backend_load",
        expected_tool_result={
            "high_active_requests": True,
            "elevated_latency": True,
        },
        remediation_tool="restart_student_api",
        remediation_description="Restart the Student Query API to clear queued requests and restore responsiveness",
        risk="LOW",
        blast_radius="Student Query API only",
    ),

    # 5 ── Backend Overload ───────────────────────────────────
    ErrorDefinition(
        name="Backend Overload",
        error_code="BACKEND_OVERLOAD",
        symptoms=[
            "Very high number of concurrent HTTP requests",
            "Increasing response times across all endpoints",
            "CPU usage elevated",
            "Some requests being dropped or queued",
        ],
        relevant_log_signals=[
            "active_http_requests > threshold",
            "high request concurrency",
            "cpu_percent > 80",
            "request queue full",
        ],
        verification_tool="check_backend_load",
        expected_tool_result={
            "high_cpu": True,
            "high_active_requests": True,
        },
        remediation_tool="restart_student_api",
        remediation_description="Restart the Student Query API to shed load and restore normal operation",
        risk="MEDIUM",
        blast_radius="Student Query API — all in-flight requests will be dropped",
    ),

    # 6 ── High CPU Usage ─────────────────────────────────────
    ErrorDefinition(
        name="High CPU Usage",
        error_code="HIGH_CPU",
        symptoms=[
            "CPU usage sustained above 80%",
            "Degraded response times",
            "Process consuming excessive CPU",
        ],
        relevant_log_signals=[
            "cpu_percent > 80",
            "high cpu",
            "resource exhaustion",
        ],
        verification_tool="check_backend_load",
        expected_tool_result={
            "high_cpu": True,
            "cpu_percent_above_80": True,
        },
        remediation_tool="restart_student_api",
        remediation_description="Restart the Student Query API to release CPU resources",
        risk="MEDIUM",
        blast_radius="Student Query API only",
    ),

    # 7 ── High Memory Usage ──────────────────────────────────
    ErrorDefinition(
        name="High Memory Usage",
        error_code="HIGH_MEMORY",
        symptoms=[
            "Memory usage growing unbounded",
            "OOM-kill risk",
            "Degraded performance due to swapping",
        ],
        relevant_log_signals=[
            "memory_mb > threshold",
            "MemoryError",
            "high memory",
        ],
        verification_tool="check_backend_load",
        expected_tool_result={
            "high_memory": True,
        },
        remediation_tool="restart_student_api",
        remediation_description="Restart the Student Query API to reclaim leaked memory",
        risk="MEDIUM",
        blast_radius="Student Query API only",
    ),

    # 8 ── Invalid SQL Query ──────────────────────────────────
    ErrorDefinition(
        name="Invalid SQL Query",
        error_code="INVALID_SQL",
        symptoms=[
            "SQL syntax errors from the LLM-generated query",
            "Specific /chat requests fail while others succeed",
            "Error contains SQL parse error or undefined column",
        ],
        relevant_log_signals=[
            "SyntaxError",
            "UndefinedColumn",
            "relation does not exist",
            "SQL parse error",
            "invalid SQL",
        ],
        verification_tool="check_db_health",
        expected_tool_result={
            "db_reachable": True,
            "can_query": True,  # DB is fine, the SQL was bad
        },
        remediation_tool="restart_student_api",
        remediation_description="Restart the Student Query API to reset LLM context (if caching bad prompts)",
        risk="LOW",
        blast_radius="Student Query API only — this is an LLM output issue, not infra",
    ),

    # 9 ── Service Unavailable ────────────────────────────────
    ErrorDefinition(
        name="Service Unavailable",
        error_code="SERVICE_UNAVAILABLE",
        symptoms=[
            "Health check endpoint returns unhealthy or unreachable",
            "HTTP 503 responses",
            "Frontend cannot reach backend at all",
        ],
        relevant_log_signals=[
            "503 Service Unavailable",
            "connection refused on backend port",
            "health check failed",
        ],
        verification_tool="check_backend_load",
        expected_tool_result={
            "service_unreachable": True,
        },
        remediation_tool="restart_student_api",
        remediation_description="Restart the Student Query API service",
        risk="LOW",
        blast_radius="Student Query API only",
    ),

    # 10 ── Dependency Failure ────────────────────────────────
    ErrorDefinition(
        name="Dependency Failure",
        error_code="DEPENDENCY_FAILURE",
        symptoms=[
            "LLM API calls failing",
            "External service timeouts",
            "Partial functionality loss",
        ],
        relevant_log_signals=[
            "LLM API error",
            "external service timeout",
            "dependency unreachable",
            "google.api_core.exceptions",
        ],
        verification_tool="check_backend_load",
        expected_tool_result={
            "dependency_errors": True,
        },
        remediation_tool="restart_student_api",
        remediation_description="Restart the Student Query API to reset external connections",
        risk="LOW",
        blast_radius="Student Query API only — depends on external service recovery",
    ),
]


# ─────────────────────────────────────────────────────────────
# Lookup helpers
# ─────────────────────────────────────────────────────────────

_BY_CODE: dict[str, ErrorDefinition] = {e.error_code: e for e in ERROR_CATALOGUE}
_BY_NAME: dict[str, ErrorDefinition] = {e.name: e for e in ERROR_CATALOGUE}


def get_error_by_code(code: str) -> ErrorDefinition | None:
    """Look up an error definition by its error_code."""
    return _BY_CODE.get(code)


def get_error_by_name(name: str) -> ErrorDefinition | None:
    """Look up an error definition by its display name."""
    return _BY_NAME.get(name)


def get_all_error_names() -> list[str]:
    """Return all registered error names."""
    return [e.name for e in ERROR_CATALOGUE]


def get_catalogue_summary() -> str:
    """
    Return a formatted text summary of the entire catalogue.
    Used as context in LLM prompts so the agents know what errors are possible.
    """
    lines: list[str] = []
    for i, e in enumerate(ERROR_CATALOGUE, 1):
        lines.append(
            f"{i}. {e.name} ({e.error_code})\n"
            f"   Symptoms: {', '.join(e.symptoms[:2])}\n"
            f"   Verification: {e.verification_tool}\n"
            f"   Remediation: {e.remediation_tool} — {e.remediation_description}\n"
            f"   Risk: {e.risk} | Blast Radius: {e.blast_radius}\n"
        )
    return "\n".join(lines)

