# Multi-Agent Incident Response System — Master Task Checklist
> **HackQubit 2.0 — Problem 18**  
> Tracks implementation progress across team members. Update checkboxes (`[ ]` → `[x]`) and status notes as each task is completed.

---

## 🌿 Team Workflow & Branching Guidelines

> [!IMPORTANT]
> 1. **Work on Dedicated Feature Branches:**
>    - Every team member must develop on their own separate feature branch. **Never commit directly to `main`**.
>    - **Shradha:** `shradha/infra-setup` or `feat/infra-vm`
>    - **Dumani:** `dumani/frontend-ui` or `feat/chatbot-ui`
>    - **Saket:** `saket/backend-api` or `feat/student-api-db`
>    - **Om:** `om/incident-pipeline` or `feat/multi-agent-response`
> 2. **Update Checklist as Work Completes:**
>    - As soon as you finish a task or subtask within your assigned scope, mark `- [ ]` → `- [x]`.
>    - Update the **Completed** count in the **Team Progress Summary** table.
> 3. **Focus on Assigned Responsibilities:**
>    - Stick to your assigned area and agreed interface contracts. Avoid editing other members' code without prior coordination.
> 4. **Merge via Pull Requests:**
>    - Verify your component and open a PR into `main` for integration. Pull/rebase `main` frequently to stay up to date.

---

## 📊 Team Progress Summary

| Member | Role / Area | Total Tasks | Completed | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Shradha** | Cloud VM, Deployment & Environment | 10 | 1 / 10 | 🟡 In Progress |
| **Dumani** | Frontend UI / UX & Email Design | 10 | 0 / 10 | 🟡 Pending |
| **Saket** | Chatbot Backend & Failure Injection | 12 | 12 / 12 | 🟢 Completed |
| **Om** | Downstream Incident Response & Agents | 14 | 14 / 14 | 🟢 Completed |
| **All** | Team Integration & End-to-End Demo | 6 | 0 / 6 | 🟡 Pending |

---

## 👤 Person 1: Shradha — Cloud VM + Deployment + Environment

**Primary Responsibility:** Infrastructure provisioning, container orchestration, host configuration, networking, log/metric pipeline access, and deployment documentation.

- [ ] **1.1 Provision Google Cloud VM**
  - [ ] Create Linux (Ubuntu LTS recommended) VM instance on GCP.
  - [ ] Configure SSH key access for all team members (Shradha, Dumani, Saket, Om).
  - [ ] Allocate static external IP or domain name.

- [ ] **1.2 Base Host Environment Setup**
  - [ ] Install Docker Engine & Docker Compose (`docker-compose-plugin`).
  - [ ] Install Python 3.10+ and Git.
  - [ ] Configure Git repository clone on VM (`/opt/HackQubit` or `~/HackQubit`).

- [ ] **1.3 Networking & Firewall Rules**
  - [ ] Restrict firewall ingress to required ports only (Frontend UI, Backend API / Chat, Incident Webhook).
  - [ ] Keep database and internal service ports isolated within Docker bridge network.
  - [ ] Ensure outbound internet connectivity for LLM API calls and email dispatch.

- [ ] **1.4 Environment Variables & Secrets Management**
  - [x] Create repository `.env.example`, `.env`, and `.gitignore` at root.
  - [ ] Configure production VM secrets (LLM API keys, SMTP credentials, DB connection strings) on the cloud VM.

- [ ] **1.5 Repository Directory Structure Setup**
  - [ ] Initialize repository structure on VM matching Section 14 of `plan.md`:
    - `frontend/`
    - `backend/`
    - `incident-response/`
    - `database/`
    - `email/`
    - `docs/`

- [ ] **1.6 Docker Compose Orchestration**
  - [ ] Author root `docker-compose.yml` linking:
    - `frontend` (Chatbot UI)
    - `backend` (Student API)
    - `database` (SQL DB)
    - `incident-response` (AI Incident Agent pipeline)
  - [ ] Configure Docker network and volume mounts for code hot-reload and persistent data.

- [ ] **1.7 Logging & Metrics Volume Mounting**
  - [ ] Mount a shared log volume (e.g., `./backend/logs` → container `/app/logs`) accessible to both backend and incident-response services.
  - [ ] Ensure incident agent can read real-time log files and query `/metrics`.

- [ ] **1.8 Security & Sandbox Isolation**
  - [ ] Ensure AI incident agents have **NO unrestricted shell access** to host VM.
  - [ ] Restrict incident system actions exclusively to allowlisted REST tools or docker container restarts.

- [ ] **1.9 Deployment Verification & Health Check**
  - [ ] Run `docker compose up --build` and verify all containers reach healthy state.
  - [ ] Share stable VM IP/URL endpoints with team.

- [ ] **1.10 Deployment Documentation**
  - [ ] Maintain `docs/deployment.md` with instructions on how to SSH, start/stop services, view logs, and redeploy.

---

## 👤 Person 2: Dumani — Frontend UI / UX & Email Design

**Primary Responsibility:** Student chatbot interface, system health/incident banner, HTML approval email template, and human-in-the-loop approval interaction.

- [ ] **2.1 Chatbot UI Layout & Component Setup**
  - [ ] Create modern, responsive UI (React / Next.js / Vue / Vite + Tailwind).
  - [ ] Implement chat window with message history container, auto-scroll, and sticky input box.

- [ ] **2.2 Chat Interaction & State Handling**
  - [ ] Implement message submission to backend `POST /chat`.
  - [ ] Render distinct bubble styles for User queries and Assistant responses.
  - [ ] Implement loading / streaming / thinking indicator while backend queries LLM/DB.

- [ ] **2.3 Chatbot Error State & Graceful Degradation**
  - [ ] Handle 500 / timeout errors gracefully with clean user error notification.
  - [ ] Ensure UI does not freeze when backend fails or connection pool exhausts.

- [ ] **2.4 System Status Indicator**
  - [ ] Add system status badge in header:
    - 🟢 `System Status: Healthy`
    - 🔴 `System Status: Incident Detected`
  - [ ] Periodically poll `GET /health` or listen to incident state.

- [ ] **2.5 Demo Query Presets (Quick Prompts)**
  - [ ] Add clickable quick query chips for demo ease:
    - *"Show students with CGPA above 8.5"*
    - *"Which students are eligible for placement?"*
    - *"Who has the highest CGPA?"*
    - *"Show CSE students"*

- [ ] **2.6 DevOps HTML Email Template Design (`email/incident_template.html`)**
  - [ ] Build responsive HTML email template compatible with major email clients.
  - [ ] Header: 🚨 `INCIDENT RESPONSE REQUIRED`, Incident ID, Severity (HIGH), Timestamp.
  - [ ] Incident Summary: Target Service, What Happened summary, Log snippet.
  - [ ] Agent Analysis: Top 3 Hypotheses with probabilities, Verification Tool results, Confirmed Root Cause (Confidence %).
  - [ ] Remediation Proposal: Action, Rationale, Risk level (LOW), Blast Radius (e.g. *Student Query API only*).

- [ ] **2.7 Interactive Approve / Reject Email Actions**
  - [ ] Add styled action buttons in email:
    - `[ APPROVE RESOLUTION ]` (Green primary button)
    - `[ REJECT RESOLUTION ]` (Red secondary button)
  - [ ] Link buttons to backend webhook URLs:
    - `POST /incidents/{incident_id}/approve`
    - `POST /incidents/{incident_id}/reject`

- [ ] **2.8 Decision Landing Page / Webhook Response UI**
  - [ ] Create a lightweight confirmation page displayed after engineer clicks Approve/Reject:
    - Showing approval confirmation timestamp, executed action, and live recovery progress.

- [ ] **2.9 Frontend API Integration with Saket**
  - [ ] Connect chat frontend to Saket's backend endpoints (`POST /chat`, `GET /health`).
  - [ ] Test cross-origin requests (CORS) handling.

- [ ] **2.10 UI Polish & Demo Readiness**
  - [ ] Polish typography, spacing, contrast, and dark/light mode aesthetics.
  - [ ] Conduct end-to-end UI walkthrough.

---

## 👤 Person 3: Saket — Chatbot Architecture + Backend

**Primary Responsibility:** Student database, backend APIs, LLM query generation, structured logging, failure simulation endpoints, and allowlisted resolution endpoints.

- [x] **3.1 PostgreSQL Database Schema & Synthetic Data Seed (`database/seed.sql`)**
  - [x] Design PostgreSQL (`pg`) table `students`:
    - `student_id` (PK, SERIAL), `name`, `department`, `year`, `cgpa` (NUMERIC), `email`, `skills` (TEXT), `placement_status`
    - Add performance indexes on `cgpa` and `department`.
  - [x] Populate database with realistic synthetic student records (50-100+ records across departments).

- [x] **3.2 Backend Service Scaffolding (FastAPI / Express / Flask)**
  - [x] Setup backend project structure (`backend/app`, `backend/routes`, `backend/services`).
  - [x] Configure PostgreSQL connection pool (e.g., `asyncpg` / `psycopg2` / SQLAlchemy pool) with configurable pool limits (e.g., `max_size=10`).

- [x] **3.3 Chatbot Endpoint (`POST /chat`) — Vectorless Structured RAG Pipeline**
  - [x] Receive natural language user question (e.g., *"which student has cgps greater than 8, and have skills in ai."*).
  - [x] **LLM Call 1 (Text-to-SQL):** Provide PostgreSQL schema in system prompt to translate question into safe SQL query.
  - [x] **Data Retrieval:** Execute generated SQL query against PostgreSQL `students` table via connection pool.
  - [x] **LLM Call 2 (Grounded Synthesis):** Pass retrieved rows + user query to LLM to generate user-friendly response.
  - [x] Format and return structured response payload (including answer, rows, generated SQL, latency) back to frontend.

- [x] **3.4 Health & Metrics Endpoints**
  - [x] `GET /health`: Returns service health status, DB connectivity status.
  - [x] `GET /metrics`: Returns latency (ms), error rate (%), active DB connections, total requests.
  - [x] `GET /students`: Simple query endpoint for direct student data inspection.

- [x] **3.5 Structured JSON Logging**
  - [x] Implement JSON logging format:
    ```json
    { "timestamp": "...", "service": "student-api", "request_id": "...", "endpoint": "/chat", "status": 500, "error": "..." }
    ```
  - [x] Write logs to shared file (`backend/logs/app.log`) and expose `GET /logs` endpoint with tail/filter support.

- [x] **3.6 Failure Simulation Endpoints (`/simulate/*`)**
  - [x] `POST /simulate/connection-exhaustion`: Exhaust DB connection pool (Primary Demo Scenario).
  - [x] `POST /simulate/db-timeout`: Introduce sleep/delay on DB queries to simulate query timeout.
  - [x] `POST /simulate/db-unavailable`: Drop DB connection / stop DB responding.
  - [x] `POST /simulate/api-delay`: Introduce heavy artificial latency.

- [x] **3.7 Verification Tool Endpoints (For Om's Agents)**
  - [x] `GET /tools/check-db-connections`: Return current active connections vs max pool limit.
  - [x] `GET /tools/check-db-health`: Return DB ping response and query latency.
  - [x] `GET /tools/check-backend-load`: Return current request queue depth and CPU/memory stats.

- [x] **3.8 Allowlisted Resolution Tool Endpoints**
  - [x] `POST /tools/restart-student-api`: Gracefully reset/restart API process or container.
  - [x] `POST /tools/clear-connection-pool`: Force-close leaked/idle DB connections and refresh pool.
  - [x] `POST /tools/scale-student-api`: Adjust worker concurrency.

- [x] **3.9 Incident Approval & Rejection Handlers**
  - [x] `POST /incidents/{id}/approve`: Validate incident ID, invoke approved resolution tool, trigger recovery verification.
  - [x] `POST /incidents/{id}/reject`: Log decision, mark incident rejected, prevent any tool execution.

- [x] **3.10 Error Handling & Connection Leak Mechanics**
  - [x] Ensure connection exhaustion scenario causes `/chat` to reliably fail with clear error signals for the detector.

- [x] **3.11 Backend Integration Tests**
  - [x] Test `/chat` with valid queries.
  - [x] Trigger `/simulate/connection-exhaustion` and verify `/chat` outputs 500 error logs.

- [x] **3.12 Backend API Documentation**
  - [x] Document all endpoints, payloads, and tool contracts for Dumani and Om.

---

## 👤 Person 4: Om — Downstream Incident-Response System

**Primary Responsibility:** Error catalogue, multi-agent pipeline (Analyzer, Hypotheses, Verification, RCA, Remediation, Safety), email alerting, and automated recovery verification.

- [x] **4.1 Comprehensive Error Catalogue Definition**
  - [x] Define structured catalogue for 10 error scenarios:
    1. Database Connection Exhaustion *(Primary demo)*
    2. Database Unavailable
    3. Database Query Timeout
    4. Backend API Timeout
    5. Backend Overload
    6. High CPU Usage
    7. High Memory Usage
    8. Invalid SQL Query
    9. Service Unavailable
    10. Dependency Failure
  - [x] For each error define: Symptoms, Log patterns, Verification tools, Expected results, Remediation action, Risk, Blast Radius.

- [x] **4.2 Incident Detector Daemon / Poller**
  - [x] Continuously monitor backend `GET /health`, `GET /metrics`, and log stream.
  - [x] Detect failure trigger (e.g. consecutive 500 errors or pool exhaustion).
  - [x] Create new Incident record with unique `incident_id`, severity `HIGH`, status `INVESTIGATING`.

- [x] **4.3 Agent 1: LLM Log Analysis Agent (`log_analyzer.py`)**
  - [x] Fetch recent logs via `GET /logs` and metrics via `GET /metrics`.
  - [x] Prompt LLM to extract key error signals, anomaly summary, and service failure context.

- [x] **4.4 Agent 2: Hypothesis Generator (`hypothesis_generator.py`)**
  - [x] Receive log analysis output.
  - [x] Generate **exactly top 3** ranked probable root causes with estimated confidence %:
    - *Hypothesis 1 (e.g. DB Connection Exhaustion - 75%)*
    - *Hypothesis 2 (e.g. DB Server Overload - 15%)*
    - *Hypothesis 3 (e.g. Backend API Overload - 10%)*

- [x] **4.5 Agent 3: Verification Tool Orchestrator (`verification_tools.py`)**
  - [x] Map each of the 3 hypotheses to its corresponding inspection tool.
  - [x] Call verification endpoints:
    - `check_db_connections()`
    - `check_db_health()`
    - `check_backend_load()`
  - [x] Collect structured verification evidence.

- [x] **4.6 Agent 4: Root Cause Analyzer (`rca_agent.py`)**
  - [x] Synthesize initial logs + metrics + 3 hypotheses + tool verification evidence.
  - [x] Confirm single supported root cause (e.g., *"Database connection pool exhausted (100/100 active)"*).
  - [x] Assign definitive confidence level (High / Medium / Low).

- [x] **4.7 Agent 5: Remediation Proposal Agent (`remediation_agent.py`)**
  - [x] Formulate safe remediation proposal matching confirmed root cause:
    - Proposed action: `restart_student_api` or `clear_connection_pool`
    - Rationale: Stale connections causing pool exhaustion
    - Risk: `LOW`
    - Blast Radius: `Student Query API only`

- [x] **4.8 Agent 6: Safety & Permission Layer (`safety_agent.py`)**
  - [x] Enforce strict allowlist check:
    - ✅ Allowed: `restart_student_api`, `clear_connection_pool`, `scale_student_api`, `check_*`
    - ❌ Prohibited: `delete_database`, `modify_student_records`, `restart_entire_vm`, arbitrary shell
  - [x] Verify target service, action allowlist, blast radius, and human approval requirement.
  - [x] Block execution if any safety rule is violated.

- [x] **4.9 Email Dispatcher Service**
  - [x] Integrate Dumani's HTML email template (`email/incident_template.html`).
  - [x] Populate template with incident ID, analysis, evidence, proposed fix, and signed approval links.
  - [x] Send email via SMTP (SendGrid, Mailgun, Gmail SMTP, or local mock for testing).

- [x] **4.10 Approval Webhook Listener & Remediation Trigger**
  - [x] Handle approve callback:
    - Validate incident state (must be `PENDING_APPROVAL`).
    - Execute allowlisted remediation tool via Saket's endpoint.
    - Transition incident status to `REMEDIATING`.
  - [x] Handle reject callback:
    - Transition incident status to `REJECTED`, record reason, abort remediation.

- [x] **4.11 Post-Remediation Recovery Verification**
  - [x] Wait for service stabilization (e.g., 3-5 seconds).
  - [x] Poll `/health`, error rate, and query latency before vs after:
    - Before: Error Rate 63%, Latency 4.8s
    - After: Error Rate < 2%, Latency ~200ms
  - [x] If recovered → Mark `INCIDENT RESOLVED` ✅.
  - [x] If not recovered → Mark `RECOVERY FAILED`, trigger escalation ⚠️.

- [x] **4.12 Incident Timeline & State Tracker (`timeline.py`)**
  - [x] Persist chronological audit timeline:
    - `INCIDENT_DETECTED` → `LOGS_ANALYZED` → `HYPOTHESES_GENERATED` → `TOOLS_VERIFIED` → `RCA_CONFIRMED` → `SAFETY_APPROVED` → `EMAIL_SENT` → `HUMAN_APPROVED` → `REMEDIATION_EXECUTED` → `RECOVERY_VERIFIED` → `RESOLVED`
  - [x] Expose `GET /incidents/{id}/timeline` for auditing/demo inspection.

- [x] **4.13 End-to-End Orchestrator (`incident_manager.py`)**
  - [x] Tie all agents into a unified pipeline runner.

- [x] **4.14 Unit & Integration Tests for Agent Pipeline**
  - [x] Mock backend failure logs and test that the 6 agents run reliably end-to-end.

---

## 🤝 Cross-Team Integration & Demo Milestones

- [ ] **M1: Interface Contracts Sign-Off (All)**
  - [ ] Saket & Om agree on `/logs`, `/metrics`, and `/tools/*` API contract.
  - [ ] Saket & Dumani agree on `/chat` and `/health` contract.
  - [ ] Dumani & Om agree on email template parameters and Approve/Reject link format.
  - [ ] Shradha shares VM environment specifications.

- [ ] **M2: Happy-Path Chatbot Baseline Working (Dumani + Saket + Shradha)**
  - [ ] Chatbot UI runs, queries backend, backend queries DB, and student data is displayed.
  - [ ] Deployed and accessible on cloud VM.

- [ ] **M3: Controlled Failure Injection Working (Saket + Shradha)**
  - [ ] Calling `POST /simulate/connection-exhaustion` causes subsequent `/chat` queries to fail.
  - [ ] Failure produces expected structured error logs.

- [ ] **M4: Automated Incident Detection & Multi-Agent Analysis (Om + Saket)**
  - [ ] Failure detection triggers incident pipeline.
  - [ ] LLM produces log summary, 3 hypotheses, runs 3 verification tools, confirms root cause.
  - [ ] Safety layer validates proposal.

- [ ] **M5: Human-in-the-Loop Email & Remediation Loop (Om + Dumani + Saket)**
  - [ ] DevOps email is received with Approve/Reject buttons.
  - [ ] Clicking Approve triggers tool execution.
  - [ ] Backend clears pool / restarts API.
  - [ ] Recovery verifier confirms health restoration and closes incident.

- [ ] **M6: Final Rehearsal & Live Presentation Polish (All)**
  - [ ] Run full live demo scenario start-to-finish without manual interventions.
  - [ ] Prepare slide deck / demo script highlighting Problem 18 requirements.

---

## 📌 How to Update This Checklist
1. As you finish a task, replace `- [ ]` with `- [x]`.
2. Update the **Team Progress Summary** table count at the top.
3. Commit changes to Git with a clear message, e.g.:
   ```bash
   git commit -am "docs(checklist): completed task 3.1 SQL database schema"
   ```

