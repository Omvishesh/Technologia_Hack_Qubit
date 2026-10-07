"""
Test script for the Incident Response Multi-Agent Pipeline.

Tests:
1. Model instantiation & validation
2. Safety agent enforcement (allowlist vs prohibited actions)
3. Email rendering (HTML template + mock generation)
4. Offline agent pipeline run (with mocked backend responses & Gemini API or fallback)
5. Timeline generation and formatting
6. Approval & Rejection flow
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from importlib import import_module

config = import_module("incident-response.config")
models = import_module("incident-response.models")
catalogue = import_module("incident-response.error_catalogue")
safety = import_module("incident-response.agents.safety_agent")
email_sender = import_module("incident-response.email_sender")
timeline = import_module("incident-response.timeline")
manager = import_module("incident-response.incident_manager")


async def test_safety_layer():
    print("\n--- 1. Testing Safety & Permission Layer ---")
    inc = models.Incident(
        error_code="DB_CONNECTION_EXHAUSTION",
        error_message="Test pool timeout",
        service="student-api",
    )
    
    # Safe action
    inc.remediation = models.Remediation(
        action="Clear connection pool",
        tool_name="clear_connection_pool",
        reason="Exhaustion",
        risk=models.RiskLevel.LOW,
        blast_radius="Student Query API only",
    )
    res = await safety.check_safety(inc)
    assert res.allowed is True, f"Expected allowed, got {res}"
    print("  [OK] Safe action 'clear_connection_pool' passed.")

    # Disallowed action
    inc.remediation = models.Remediation(
        action="Delete all records",
        tool_name="delete_database",
        reason="Reset",
        risk=models.RiskLevel.HIGH,
        blast_radius="entire system",
    )
    res = await safety.check_safety(inc)
    assert res.allowed is False, f"Expected blocked, got {res}"
    print("  [OK] Dangerous action 'delete_database' safely blocked.")


async def test_email_rendering():
    print("\n--- 2. Testing Email Renderer & Mock Dispatch ---")
    inc = models.Incident(
        error_code="DB_CONNECTION_EXHAUSTION",
        error_message="Database pool lease exhausted after 3.0s",
        service="student-api",
    )
    inc.log_summary = models.LogSummary(
        summary="High surge in student queries led to active connection exhaustion.",
        error_signals=["PoolTimeoutError", "db_pool_active=10"],
        error_count=15,
        dominant_error="PoolTimeoutError",
    )
    inc.hypotheses = [
        models.Hypothesis(
            rank=1,
            title="Database Connection Pool Exhaustion",
            description="Lease timeout in asyncpg pool",
            confidence=0.85,
            verification_tool="check_db_connections",
            expected_if_true="pool_exhausted=true",
        ),
        models.Hypothesis(
            rank=2,
            title="Database Server Unresponsive",
            description="Postgres instance overloaded",
            confidence=0.10,
            verification_tool="check_db_health",
            expected_if_true="ping_latency > 1000ms",
        ),
        models.Hypothesis(
            rank=3,
            title="Backend Thread Starvation",
            description="High CPU usage causing slow handling",
            confidence=0.05,
            verification_tool="check_backend_load",
            expected_if_true="cpu_percent > 80%",
        ),
    ]
    inc.verification_results = [
        models.ToolResult(
            tool_name="check_db_connections",
            success=True,
            result={"active_connections": 10, "max_pool_size": 10, "pool_exhausted": True},
        )
    ]
    inc.root_cause = models.RootCause(
        cause="Database connection pool exhausted",
        evidence=["10/10 active connections in pool", "Waiting requests queue > 0"],
        confidence=0.95,
        confirmed_hypothesis_rank=1,
    )
    inc.remediation = models.Remediation(
        action="Clear and recycle PostgreSQL connection pool",
        tool_name="clear_connection_pool",
        reason="Drop stale leaked connections",
        risk=models.RiskLevel.LOW,
        blast_radius="Student Query API only",
    )
    
    sent = await email_sender.send_approval_email(inc)
    assert sent is True, "Failed to send/mock email"
    email_path = Path(f"incident-response/emails/{inc.id}.html")
    assert email_path.exists(), f"Email file not written to {email_path}"
    print(f"  [OK] Mock approval email generated successfully at: {email_path}")


async def test_simulated_pipeline():
    print("\n--- 3. Testing Full Incident Manager Pipeline (Mocked Backend HTTP) ---")
    mock_logs = [
        {
            "timestamp": "2026-10-07T14:15:30.124Z",
            "service": "student-api",
            "endpoint": "/chat",
            "status": 500,
            "error": "asyncpg.exceptions.PoolTimeoutError: Timeout waiting for connection from pool after 3.0s",
            "db_pool_active": 10,
            "db_pool_max": 10,
        }
    ]
    mock_metrics = {
        "cpu_percent": 22.4,
        "memory_mb": 180.5,
        "active_http_requests": 8,
        "db_pool_active": 10,
        "db_pool_max": 10,
        "error_rate": 0.75,
    }

    mock_db_conn_res = models.ToolResult(
        tool_name="check_db_connections",
        success=True,
        result={"active_connections": 10, "max_pool_size": 10, "pool_exhausted": True},
    )
    mock_db_health_res = models.ToolResult(
        tool_name="check_db_health",
        success=True,
        result={"db_reachable": True, "ping_latency_ms": 3.5, "can_query": False},
    )
    mock_backend_load_res = models.ToolResult(
        tool_name="check_backend_load",
        success=True,
        result={"cpu_percent": 21.0, "memory_mb": 180.0, "active_http_requests": 6},
    )

    async def mock_tool_call(tool_name: str):
        if tool_name == "check_db_connections":
            return mock_db_conn_res
        elif tool_name == "check_db_health":
            return mock_db_health_res
        return mock_backend_load_res

    with patch.object(manager, "collect_logs", AsyncMock(return_value={"success": True, "logs": mock_logs, "count": 1})), \
         patch.object(manager, "collect_metrics", AsyncMock(return_value={"success": True, "metrics": mock_metrics})), \
         patch.object(manager, "execute_verifications", AsyncMock(return_value=[mock_db_conn_res, mock_db_health_res, mock_backend_load_res])), \
         patch.object(manager, "call_remediation_tool", AsyncMock(return_value=models.ToolResult(tool_name="clear_connection_pool", success=True))), \
         patch.object(manager, "verify_recovery", AsyncMock(return_value=models.RecoveryResult(recovered=True, health_check_passed=True, details="Error rate: 75% -> 0%"))):

        inc = models.Incident(
            error_code="DB_CONNECTION_EXHAUSTION",
            error_message="Timeout waiting for connection from pool",
            service="student-api",
        )

        analyzed_inc = await manager.run_pipeline(inc)
        assert analyzed_inc.status == models.IncidentStatus.AWAITING_APPROVAL
        print(f"  [OK] Pipeline finished up to approval. Status: {analyzed_inc.status.value}")
        print(f"      Root Cause: {analyzed_inc.root_cause.cause} ({analyzed_inc.root_cause.confidence:.0%})")
        print(f"      Proposed Fix: {analyzed_inc.remediation.action} ({analyzed_inc.remediation.tool_name})")
        print(f"      Safety: Allowed={analyzed_inc.safety_check.allowed}")

        # Simulate Approval
        approved_inc = await manager.approve_incident(analyzed_inc.id, approved_by="DevOps SRE")
        assert approved_inc.status == models.IncidentStatus.RESOLVED
        print(f"  [OK] Approved incident executed remediation & recovered: {approved_inc.status.value}")
        print(f"      Timeline events recorded: {len(approved_inc.timeline)}")


async def main():
    await test_safety_layer()
    await test_email_rendering()
    await test_simulated_pipeline()
    print("\nALL TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
