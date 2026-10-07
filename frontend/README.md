# 🎓 Campus AI Assistant — Frontend UI / UX
## HackQubit 2.0 (Problem 18) — Autonomous Multi-Agent Incident Response System
**Role:** Person 2 — Dumani (Frontend UI / UX)  
**Assigned Branch:** `frontend`  
**Working Directory:** `Technologia_Hack_Qubit/`

---

## 📋 Comprehensive Implementation Checklist (Sections 2.1 – 2.10)

### ✅ 2.1 Chatbot UI Layout & Component Setup
- **Technology:** Modern, responsive dark-mode web application (Vite / Tailwind / Modern CSS).
- **Layout:** Chat window with message history container, auto-scroll to bottom, sticky header with branding, and sticky bottom input bar.
- **Files:** [`frontend/chatbot-ui/index.html`](file:///c:/Users/Duman/OneDrive/Desktop/JSR/Technologia_Hack_Qubit/frontend/chatbot-ui/index.html) and [`frontend/chatbot-ui/css/style.css`](file:///c:/Users/Duman/OneDrive/Desktop/JSR/Technologia_Hack_Qubit/frontend/chatbot-ui/css/style.css).

### ✅ 2.2 Chat Interaction & State Handling
- **API Client:** Submits user queries to backend `POST /chat` with JSON body `{"query": "..."}`.
- **Bubble Styles:** Distinct visual cards for User queries (`.message-row.user`, blue bubble) and Assistant responses (`.message-row.assistant`, slate card).
- **Data Rendering:** Rich tabular formatting for student records (Student ID, Name, Department, Year, CGPA, Placement status).
- **Thinking / Loading Indicator:** Animated pulsating bouncing dots (`#typing-indicator`) showing `"Querying student database..."`.

### ✅ 2.3 Chatbot Error State & Graceful Degradation
- **Non-blocking Error Handling:** Intercepts 500 error / connection timeouts gracefully without freezing the UI.
- **Error Trace Display:** Renders clear incident card (`sqlalchemy.exc.TimeoutError - QueuePool limit 10 reached`) with direct CTA to open the DevOps Incident Portal.
- **Offline Mock / Demo Mode:** Built-in fallback so the UI operates smoothly even when backend services are down.

### ✅ 2.4 System Status Indicator
- **Live Header Badge:**
  - `🟢 System Status: Healthy (180ms)`
  - `🔴 System Status: Incident Detected (100/100 Connections)`
- **Poller:** Background interval polling `GET /health` with automatic status flipping and alert banner display.

### ✅ 2.5 Demo Query Presets (Quick Prompts)
Interactive 1-click prompt chips embedded in the bottom toolbar:
1. `"📊 Show students with CGPA above 8.5"`
2. `"💼 Which students are eligible for placement?"`
3. `"🏆 Who has the highest CGPA?"`
4. `"💻 Show CSE students"`
5. `"📈 CGPA > 9.0 count"`
6. `"⚡ Simulate DB Connection Failure"` (Primary Hackathon Demo Trigger)

### ✅ 2.6 DevOps HTML Email Template Design
- **File:** [`email/incident_template.html`](file:///c:/Users/Duman/OneDrive/Desktop/JSR/Technologia_Hack_Qubit/email/incident_template.html)
- **Email Compatibility:** Inline styles with full table layout support for Gmail, Outlook, Apple Mail.
- **Header:** `🚨 Human Approval Required`, Incident ID (`INC-2026-018`), Severity (`HIGH`), Detection Timestamp.
- **Summary:** Service (`student-api`), What happened, Log snippet.
- **Multi-Agent Diagnostics:** Top 3 Hypotheses with probabilities, Tool verification results, Confirmed Root Cause with confidence percentage.
- **Remediation Proposal:** Action (`restart_student_api()`), Rationale, Risk level (`LOW`), Blast Radius (`student-api container only`).

### ✅ 2.7 Interactive Approve / Reject Email Actions
- **Styled Buttons:**
  - `[ ✅ APPROVE RESOLUTION ]` — High-contrast Green primary button (`#059669` / `#10b981`).
  - `[ ❌ REJECT RESOLUTION ]` — High-contrast Red secondary button (`#dc2626` / `#b91c1c`).
- **Webhook Integration:** Targets `POST /incidents/{incident_id}/approve` and `POST /incidents/{incident_id}/reject` or decision confirmation URLs.

### ✅ 2.8 Decision Landing Page / Webhook Response UI
- **File:** [`frontend/chatbot-ui/decision-landing.html`](file:///c:/Users/Duman/OneDrive/Desktop/JSR/Technologia_Hack_Qubit/frontend/chatbot-ui/decision-landing.html)
- **Features:**
  - Dynamic confirmation banner based on `?action=approve` or `?action=reject`.
  - Approval timestamp, Incident ID, and Authorized Action.
  - Live 4-step execution and health recovery stepper:
    1. Human Approval Gate Passed
    2. Allowlist & Safety Verification
    3. Tool Execution (`restart_student_api()`)
    4. Health Recovery Verification (`GET /health` 200 OK)
  - Telemetry Before vs. After comparison (Error rate: 63.2% &rarr; 0.0%, Latency: 4,850ms &rarr; 180ms, Connections: 100/100 &rarr; 14/100).

### ✅ 2.9 Frontend API Integration with Saket
- **Configurable Backend Base URL:** Defaults to `http://localhost:8000` or Cloud VM IP (`http://<VM_IP>:8000`) stored in `localStorage`.
- **CORS Handling:** Configured for cross-origin JSON requests with proper headers.

### ✅ 2.10 UI Polish & Demo Readiness
- Glassmorphism dark aesthetic with high-contrast accents.
- Smooth CSS animations (`@keyframes fade-in`, `@keyframes slide-down`, pulsing dots).
- High-resolution visual mockup image generated at [`frontend/frontend_ui_structure.png`](file:///c:/Users/Duman/OneDrive/Desktop/JSR/Technologia_Hack_Qubit/frontend/frontend_ui_structure.png).

---

## 🏃 Quick Start Guide

### 1. Launch in Browser (Zero Setup)
Double-click or open in Chrome / Edge:
```text
Technologia_Hack_Qubit/frontend/chatbot-ui/index.html
```

### 2. Run with Node / Vite
```bash
cd frontend/chatbot-ui
npm install
npm run dev
```
