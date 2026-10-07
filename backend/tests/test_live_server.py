"""
End-to-End Live API Test Runner for student-api backend.
Tests all endpoints on http://localhost:8000.
"""
import httpx
import json

BASE_URL = "http://localhost:8000"

def test_pipeline():
    client = httpx.Client(base_url=BASE_URL, timeout=20.0)

    # 1. Root
    print("--> 1. Testing GET /")
    r = client.get("/")
    print("Status:", r.status_code, "| Service:", r.json().get("service"))
    assert r.status_code == 200

    # 2. Health
    print("\n--> 2. Testing GET /health")
    r = client.get("/health")
    print("Status:", r.status_code, "| Health:", r.json())
    assert r.status_code == 200
    assert r.json()["database"]["can_query"] is True

    # 3. Students inspection
    print("\n--> 3. Testing GET /students?limit=2")
    r = client.get("/students?limit=2")
    print("Status:", r.status_code, "| Count:", r.json()["count"])
    for s in r.json()["students"]:
        print(f"   - {s['name']} ({s['department']}) | CGPA: {s['cgpa']}")
    assert r.status_code == 200

    # 4. Live Chatbot RAG
    print("\n--> 4. Testing POST /chat (Live Vectorless RAG via Groq)")
    query = "which student has cgps greater than 8, and have skills in ai."
    r = client.post("/chat", json={"query": query})
    print("Status:", r.status_code)
    data = r.json()
    print("Generated SQL:", data["metadata"]["generated_sql"])
    print("Row Count:", data["metadata"]["row_count"])
    print("Latency:", data["metadata"]["latency_ms"], "ms")
    print("Answer Preview:\n", data["response"][:200], "...")
    assert r.status_code == 200

    # 5. Metrics
    print("\n--> 5. Testing GET /metrics")
    r = client.get("/metrics")
    print("Metrics:", r.json())
    assert r.status_code == 200

    # 6. Structured Logs
    print("\n--> 6. Testing GET /logs?limit=2")
    r = client.get("/logs?limit=2")
    print(f"Retrieved {len(r.json()['logs'])} logs. Last endpoint: {r.json()['logs'][-1]['endpoint']}")
    assert r.status_code == 200

    # 7. Failure Injection
    print("\n--> 7. Testing POST /simulate/connection-exhaustion (Failure Demo)")
    r = client.post("/simulate/connection-exhaustion")
    print("Simulation status:", r.json()["scenario"])
    assert r.status_code == 200

    # 8. Incident Diagnostic Tool
    print("\n--> 8. Testing GET /tools/check-db-connections")
    r = client.get("/tools/check-db-connections")
    print("Tool check: pool_exhausted =", r.json()["pool_exhausted"])
    assert r.json()["pool_exhausted"] is True

    # 9. Verify Chat Fails with 500
    print("\n--> 9. Testing POST /chat during outage (Expect 500 DB_CONNECTION_TIMEOUT)")
    r = client.post("/chat", json={"query": "who has highest cgpa"})
    print("Status:", r.status_code, "| Error code:", r.json()["error_code"])
    assert r.status_code == 500
    assert r.json()["error_code"] == "DB_CONNECTION_TIMEOUT"

    # 10. Automated Remediation Tool
    print("\n--> 10. Testing POST /tools/clear-connection-pool (Remediation)")
    r = client.post("/tools/clear-connection-pool")
    print("Remediation status:", r.json()["status"])
    assert r.status_code == 200

    # 11. Verify Recovery
    print("\n--> 11. Testing POST /chat post-remediation (Expect 200 OK)")
    r = client.post("/chat", json={"query": "who has highest cgpa"})
    print("Status:", r.status_code, "| Status:", r.json()["status"])
    assert r.status_code == 200

    # 12. Human-in-the-Loop Incident Approval
    print("\n--> 12. Testing POST /incidents/INC-DEMO-01/approve")
    r = client.post("/incidents/INC-DEMO-01/approve", json={"action": "clear-connection-pool", "approved_by": "devops-lead"})
    print("Status:", r.status_code, "| Result:", r.json()["status"])
    assert r.status_code == 200

    print("\n" + "=" * 45)
    print("   ALL 12 ENDPOINTS LIVE & VERIFIED! [OK]   ")
    print("=" * 45)

if __name__ == "__main__":
    test_pipeline()
