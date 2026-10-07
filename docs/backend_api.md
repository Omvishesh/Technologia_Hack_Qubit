# Student Chatbot Backend API Documentation (`student-api`)
> **HackQubit 2.0 — Problem 18**  
> Component Owner: **Saket (Person 3 — Chatbot Architecture + Backend)**  
> Service Host: `http://localhost:8000` (Swagger UI: `http://localhost:8000/docs`)

---

## 📌 Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Database Schema (`students` table)](#2-database-schema)
3. [Chatbot Vectorless RAG API (`POST /chat`)](#3-chatbot-vectorless-rag-api)
4. [Health & Observability APIs](#4-health--observability-apis)
5. [Failure Simulation Suite (`POST /simulate/*`)](#5-failure-simulation-suite)
6. [Incident Agent Tool Contracts (`GET /tools/*`, `POST /tools/*`)](#6-incident-agent-tool-contracts)
7. [Human-in-the-Loop Incident Approval APIs (`/incidents/*`)](#7-human-in-the-loop-incident-approval-apis)
8. [Structured Log Format (`backend/logs/app.log`)](#8-structured-log-format)

---

## 1. Architecture Overview

The backend uses **Vectorless Structured RAG (Text-to-SQL)**:
1. Natural language questions are converted into deterministic, safe `SELECT` SQL queries.
2. The query executes against the structured student database.
3. The retrieved records are synthesized into a friendly response.
4. If connection pool exhaustion or database failure occurs, structured error events are written to `backend/logs/app.log` and surfaced to downstream multi-agent monitors.

---

## 2. Database Schema

**Table:** `students`

| Field | Type | Attributes | Description |
| :--- | :--- | :--- | :--- |
| `student_id` | `VARCHAR(20)` | `PRIMARY KEY` | Student ID (e.g. `STU001`) |
| `name` | `VARCHAR(100)` | `NOT NULL` | Full Name |
| `department` | `VARCHAR(50)` | `NOT NULL` | Academic Dept |
| `year` | `INTEGER` | `NOT NULL` | Academic Year (1-4) |
| `cgpa` | `REAL` | `NOT NULL` | CGPA (0.00 - 10.00) |
| `email` | `VARCHAR(120)` | `NOT NULL, UNIQUE` | University Email |
| `skills` | `TEXT` | `NOT NULL` | Comma-delimited skills |
| `placement_status` | `VARCHAR(20)` | `NOT NULL` | `Placed`, `Eligible`, `Not Eligible` |

---

## 3. Chatbot Vectorless RAG API

### `POST /chat`
Processes natural language student inquiries.

#### Request Body
```json
{
  "query": "which student has cgps greater than 8, and have skills in ai."
}
```

#### Success Response (`200 OK`)
```json
{
  "status": "success",
  "query": "which student has cgps greater than 8, and have skills in ai.",
  "response": "Found 3 student(s) matching your request:\n1. **Meera Rao** (Computer Science, Year 4) — **CGPA: 9.78** | Skills: *Machine Learning, AI, Rust, C++, LLMs* | Status: `Placed`\n...",
  "data": [
    {
      "student_id": "STU008",
      "name": "Meera Rao",
      "department": "Computer Science",
      "year": 4,
      "cgpa": 9.78,
      "email": "meera.rao@campus.edu",
      "skills": "Machine Learning, AI, Rust, C++, LLMs",
      "placement_status": "Placed"
    }
  ],
  "metadata": {
    "generated_sql": "SELECT student_id, name, department, year, cgpa, email, skills, placement_status FROM students WHERE cgpa > 8.0 AND LOWER(skills) LIKE '%ai%' ORDER BY cgpa DESC LIMIT 20",
    "row_count": 1,
    "latency_ms": 3.45
  }
}
```

#### Error Response (`500 Internal Server Error`)
*(Occurs during simulated connection exhaustion or DB outage)*
```json
{
  "status": "error",
  "error_code": "DB_CONNECTION_TIMEOUT",
  "message": "Failed to execute database query: connection pool exhausted (Timeout waiting for connection from pool after 3.0s)",
  "request_id": "req-09a980c8"
}
```

---

## 4. Health & Observability APIs

### `GET /health`
Returns service liveness and database probe result:
```json
{
  "status": "healthy",
  "service": "student-api",
  "database": {
    "db_reachable": true,
    "ping_latency_ms": 1.25,
    "can_query": true,
    "error": null
  }
}
```

### `GET /metrics`
Returns system metrics:
```json
{
  "uptime_seconds": 128.5,
  "total_requests": 25,
  "total_errors": 2,
  "error_rate_percent": 8.0,
  "avg_latency_ms": 14.5,
  "active_db_connections": 1,
  "max_db_connections": 5,
  "pool_exhausted": false,
  "waiting_requests": 0
}
```

### `GET /students`
Direct row inspector for UI or testing.
- Parameters: `limit` (default 20), `offset` (default 0), `department` (optional filter).

### `GET /logs`
Returns tail of structured JSON application logs.
- Parameters: `limit` (default 50), `status` (optional filter, e.g. `status=500`).

---

## 5. Failure Simulation Suite (`POST /simulate/*`)

Used for controlled incident demonstration:

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/simulate/connection-exhaustion` | `POST` | Primary incident: saturates all pool slots causing `/chat` queries to fail with 500. |
| `/simulate/db-timeout` | `POST` | Injects synthetic delay > timeout threshold into database queries. |
| `/simulate/db-unavailable` | `POST` | Simulates database host crash / port unreachable. |
| `/simulate/api-delay` | `POST` | Injects heavy HTTP processing latency. |
| `/simulate/invalid-sql` | `POST` | Injects malformed SQL generation error. |
| `/simulate/reset` | `POST` | Clears all simulated faults and recycles connection pool. |

---

## 6. Incident Agent Tool Contracts (`/tools/*`)

Dedicated endpoints for Om's multi-agent system:

### Read-Only Verification Tools
- `GET /tools/check-db-connections`:
  ```json
  {
    "active_connections": 5,
    "max_pool_size": 5,
    "waiting_requests": 2,
    "pool_exhausted": true
  }
  ```
- `GET /tools/check-db-health`:
  ```json
  {
    "db_reachable": true,
    "ping_latency_ms": 3000.1,
    "can_query": false,
    "error": "PoolTimeoutError: Active pool exhausted"
  }
  ```
- `GET /tools/check-backend-load`:
  ```json
  {
    "cpu_percent": 12.4,
    "memory_mb": 65.3,
    "active_http_requests": 34
  }
  ```

### Allowlisted Remediation Tools
- `POST /tools/clear-connection-pool`: Force drops hung connections and creates fresh pool.
- `POST /tools/restart-student-api`: Gracefully restarts process runtime and recycles pool.
- `POST /tools/scale-student-api`: Dynamically resizes connection pool (Body: `{"pool_size": 10}`).

---

## 7. Human-in-the-Loop Incident Approval APIs

### `POST /incidents/{incident_id}/approve`
Executes remediation action once approved by human operator or email link.
```json
// Body:
{
  "action": "clear-connection-pool",
  "approved_by": "devops-engineer@hackqubit.local"
}
```

### `POST /incidents/{incident_id}/reject`
Rejects automated action and logs audit record.
```json
// Body:
{
  "rejected_by": "devops-engineer@hackqubit.local",
  "reason": "False alarm or manual maintenance planned"
}
```

---

## 8. Structured Log Format

Every request writes a single JSON line to `backend/logs/app.log`:
```json
{
  "timestamp": "2026-10-07T09:08:03.545586+00:00",
  "service": "student-api",
  "request_id": "req-09a980c8",
  "endpoint": "/chat",
  "user_query": "which student has cgps greater than 8",
  "generated_sql": "SELECT ... FROM students WHERE cgpa > 8.0 ...",
  "db_pool_active": 5,
  "db_pool_max": 5,
  "status": 500,
  "error": "TimeoutError: PoolTimeoutError: Timeout waiting for connection from pool after 3.0s (active: 5/5)",
  "latency_ms": 3000.75
}
```
