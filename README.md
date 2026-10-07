# Technologia_Hack_Qubit (HackQubit 2.0 — Problem 18)
## Multi-Agent Autonomous Incident Response System

This repository contains the end-to-end implementation for **Problem 18**: an autonomous multi-agent incident-response system for a campus student-data chatbot application.

---

### 👥 Team Responsibilities (from plan.md)
- **Person 1 — Shradha:** Cloud VM, Deployment, Docker Compose, controlled failure injection.
- **Person 2 — Dumani:** Frontend UI/UX, Campus Chatbot interface, System health banner, HTML approval email template, and human-in-the-loop decision landing UI. *(Completed on `frontend` branch)*
- **Person 3 — Saket:** Chatbot Architecture, SQL database, `POST /chat`, `GET /health`, failure simulation endpoints.
- **Person 4 — Om:** Downstream AI Incident-Response pipeline, Log Analysis Agent, Hypothesis Generator, Verification Tools, Root Cause Analyzer, Remediation Agent, Safety Layer.

---

### 📂 Repository Structure
```text
Technologia_Hack_Qubit/
├── frontend/
│   ├── chatbot-ui/
│   │   ├── index.html               # Campus AI Assistant & Incident Portal
│   │   ├── decision-landing.html    # Standalone DevOps Decision & Recovery Page
│   │   ├── css/
│   │   │   └── style.css            # Dark DevOps theme & responsive styles
│   │   ├── js/
│   │   │   ├── app.js               # Application client, state & live API connection
│   │   │   └── mockData.js          # Student dataset & offline demo engine
│   │   ├── vite.config.js           # Vite dev server & CORS proxy config
│   │   └── package.json             # Scripts & dependencies
│   ├── decision-landing.html        # Root decision landing page
│   ├── frontend_ui_structure.png    # High-resolution visual UI structure image
│   └── README.md                    # Detailed frontend documentation (2.1 - 2.10)
│
├── email/
│   └── incident_template.html       # Responsive DevOps Approval Email template
│
├── plan.md                          # Hackathon Master Plan
└── README.md
```

---

### 🚀 Running the Frontend
- **Zero-Install (Browser):** Open [`frontend/chatbot-ui/index.html`](frontend/chatbot-ui/index.html) directly in Chrome or Edge.
- **Dev Server (Node/Vite):**
  ```bash
  cd frontend/chatbot-ui
  npm install
  npm run dev
  ```
- **Python Server:**
  ```bash
  python -m http.server 3000 --directory frontend/chatbot-ui
  ```
