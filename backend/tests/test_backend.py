"""
Comprehensive integration tests for Student Chatbot Backend API.
Tests end-to-end RAG pipeline, failure simulation, verification tools, and incident resolution.
"""
import unittest
import os
import json
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app
from backend.database.connection import db_manager

class BackendIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Ensure clean initial state
        db_manager.clear_pool()

    def tearDown(self):
        # Reset simulated failures between tests
        db_manager.clear_pool()

    def test_01_health_endpoint(self):
        """Test GET /health returns healthy status and DB reachable."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["database"]["db_reachable"])
        self.assertTrue(data["database"]["can_query"])

    def test_02_direct_students_query(self):
        """Test GET /students returns seeded records."""
        res = self.client.get("/students?limit=5")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["count"], 0)
        self.assertIn("students", data)
        first = data["students"][0]
        self.assertIn("student_id", first)
        self.assertIn("name", first)
        self.assertIn("cgpa", first)

    def test_03_chat_rag_pipeline(self):
        """Test POST /chat with natural language query returns structured answer and generated SQL."""
        query_payload = {"query": "which student has cgps greater than 8, and have skills in ai."}
        res = self.client.post("/chat", json=query_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("response", data)
        self.assertIn("data", data)
        self.assertIn("metadata", data)
        self.assertTrue("cgpa" in data["metadata"]["generated_sql"].lower())
        self.assertGreater(len(data["data"]), 0)

    def test_04_structured_logging(self):
        """Test GET /logs returns structured JSON entries."""
        res = self.client.get("/logs?limit=5")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("logs", data)
        self.assertGreaterEqual(len(data["logs"]), 1)
        last_log = data["logs"][-1]
        self.assertEqual(last_log["service"], "student-api")
        self.assertIn("status", last_log)

    def test_05_metrics_endpoint(self):
        """Test GET /metrics returns throughput and pool status."""
        res = self.client.get("/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_requests", data)
        self.assertIn("error_rate_percent", data)
        self.assertIn("active_db_connections", data)

    def test_06_connection_exhaustion_simulation(self):
        """
        Primary Demo Scenario:
        1. Inject connection exhaustion.
        2. Verify diagnostic tools reflect pool saturation.
        3. Verify POST /chat fails with HTTP 500 DB_CONNECTION_TIMEOUT.
        4. Clear connection pool using resolution tool.
        5. Verify POST /chat succeeds again.
        """
        # Step 1: Simulate connection exhaustion
        sim_res = self.client.post("/simulate/connection-exhaustion")
        self.assertEqual(sim_res.status_code, 200)
        self.assertEqual(sim_res.json()["scenario"], "DATABASE_CONNECTION_EXHAUSTION")

        # Step 2: Verification tool check
        tool_res = self.client.get("/tools/check-db-connections")
        self.assertEqual(tool_res.status_code, 200)
        self.assertTrue(tool_res.json()["pool_exhausted"])

        # Step 3: POST /chat should fail with 500
        chat_res = self.client.post("/chat", json={"query": "which student has cgps greater than 8"})
        self.assertEqual(chat_res.status_code, 500)
        err_data = chat_res.json()
        self.assertEqual(err_data["status"], "error")
        self.assertEqual(err_data["error_code"], "DB_CONNECTION_TIMEOUT")

        # Step 4: Resolution tool execution
        resolve_res = self.client.post("/tools/clear-connection-pool")
        self.assertEqual(resolve_res.status_code, 200)
        self.assertEqual(resolve_res.json()["status"], "success")

        # Step 5: Verification that service recovered
        recovery_res = self.client.post("/chat", json={"query": "which student has cgps greater than 8"})
        self.assertEqual(recovery_res.status_code, 200)
        self.assertEqual(recovery_res.json()["status"], "success")

    def test_07_incident_approval_handler(self):
        """Test POST /incidents/{id}/approve applies remediation."""
        # Inject failure
        self.client.post("/simulate/connection-exhaustion")

        # Call approval endpoint
        app_res = self.client.post(
            "/incidents/INC-8891/approve",
            json={"action": "clear-connection-pool", "approved_by": "devops-engineer@hackqubit.local"}
        )
        self.assertEqual(app_res.status_code, 200)
        data = app_res.json()
        self.assertEqual(data["status"], "approved_and_executed")
        self.assertTrue(data["recovered"])

        # Verify system is healthy
        health = self.client.get("/health").json()
        self.assertEqual(health["status"], "healthy")

    def test_08_incident_rejection_handler(self):
        """Test POST /incidents/{id}/reject marks incident rejected."""
        rej_res = self.client.post(
            "/incidents/INC-8892/reject",
            json={"rejected_by": "lead-engineer@hackqubit.local", "reason": "Awaiting manual audit"}
        )
        self.assertEqual(rej_res.status_code, 200)
        data = rej_res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIsNone(data["action_executed"])

if __name__ == "__main__":
    unittest.main()
