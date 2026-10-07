const getMockData = (query) => {
  if (typeof window !== 'undefined' && typeof window.getMockResponse === 'function') {
    return window.getMockResponse(query);
  }
  return {
    success: true,
    query: `SELECT * FROM students WHERE query LIKE '%${query}%';`,
    latency_ms: 120,
    summary: `Found student records matching "${query}":`,
    students: (typeof window !== 'undefined' && window.MOCK_STUDENTS) ? window.MOCK_STUDENTS : []
  };
};

// Application Configuration
const CONFIG = {
  mode: localStorage.getItem('app_mode') || 'demo', // 'demo' or 'live'
  backendUrl: localStorage.getItem('backend_url') || 'http://localhost:8000',
  pollInterval: parseInt(localStorage.getItem('poll_interval') || '5', 10),
  activeIncident: false
};

// Global State
let currentIncident = null;

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initUI();
  renderEmailPreview();
  startHealthPoller();
});

// UI Initialization
function initUI() {
  updateStatusBadge(false);
  document.getElementById('mode-label').textContent = CONFIG.mode === 'live' ? 'Live API' : 'Demo Mode';
  document.getElementById('config-mode').value = CONFIG.mode;
  document.getElementById('config-backend-url').value = CONFIG.backendUrl;
  document.getElementById('config-poll-interval').value = CONFIG.pollInterval;
  
  if (CONFIG.mode === 'live') {
    document.getElementById('endpoint-status').innerHTML = `Target: <code style="color: #38bdf8;">${CONFIG.backendUrl}/chat</code>`;
  }
}

// Tab View Switcher
function switchView(viewName) {
  const chatView = document.getElementById('chat-view');
  const devopsView = document.getElementById('devops-view');
  const tabChat = document.getElementById('tab-chat');
  const tabDevops = document.getElementById('tab-devops');

  if (viewName === 'chat') {
    chatView.classList.remove('hidden');
    devopsView.classList.add('hidden');
    tabChat.classList.add('active');
    tabDevops.classList.remove('active');
  } else {
    chatView.classList.add('hidden');
    devopsView.classList.remove('hidden');
    tabChat.classList.remove('active');
    tabDevops.classList.add('active');
  }
}
window.switchView = switchView;

// Quick Prompt Handler
function handlePromptClick(promptText) {
  const input = document.getElementById('user-input');
  input.value = promptText;
  handleChatSubmit(new Event('submit'));
}
window.handlePromptClick = handlePromptClick;

// Chat Submission
export async function handleChatSubmit(e) {
  if (e && e.preventDefault) e.preventDefault();
  const input = document.getElementById('user-input');
  const query = input.value.trim();
  if (!query) return;

  // Add User Message
  appendUserMessage(query);
  input.value = '';

  // Show Typing Indicator
  const typingIndicator = document.getElementById('typing-indicator');
  typingIndicator.style.display = 'flex';
  scrollToBottom();

  if (CONFIG.mode === 'demo') {
    setTimeout(() => {
      typingIndicator.style.display = 'none';

      // If active incident exists, simulate a backend 500 failure
      if (CONFIG.activeIncident) {
        appendIncidentErrorResponse(query);
      } else {
        const mockRes = getMockData(query);
        appendBotResponse(mockRes);
      }
    }, 600);
  } else {
    // Live API mode (with 10s timeout to gracefully catch DB pool exhaustion)
    try {
      const response = await fetch(`${CONFIG.backendUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, message: query }),
        signal: AbortSignal.timeout(10000)
      });

      typingIndicator.style.display = 'none';

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        triggerIncidentMode(errData.detail || 'Database Connection Pool Exhausted (HTTP 500)');
        appendIncidentErrorResponse(query, errData);
      } else {
        const data = await response.json();
        appendBotResponse(data);
      }
    } catch (err) {
      typingIndicator.style.display = 'none';
      triggerIncidentMode('Backend Unreachable or Connection Timeout');
      appendIncidentErrorResponse(query, { error: err.message });
    }
  }
}
window.handleChatSubmit = handleChatSubmit;

// Message Appenders
function appendUserMessage(text) {
  const container = document.getElementById('messages-container');
  const row = document.createElement('div');
  row.className = 'message-row user';
  row.innerHTML = `
    <div class="avatar user-avatar">👤</div>
    <div class="message-bubble">
      <p>${escapeHTML(text)}</p>
      <div class="message-meta">${formatTime()}</div>
    </div>
  `;
  container.appendChild(row);
  scrollToBottom();
}

function appendBotResponse(data) {
  const container = document.getElementById('messages-container');
  const row = document.createElement('div');
  row.className = 'message-row assistant';

  const studentList = data.students || data.data || data.results || data.records || [];
  const summaryText = data.summary || data.response || data.reply || data.message || 'Here are the matching records from the student database:';
  const queryStr = data.query || data.sql || data.executed_query || null;

  let studentTableHTML = '';
  if (studentList && studentList.length > 0) {
    studentTableHTML = `
      <div class="data-table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Department</th>
              <th>Year</th>
              <th>CGPA</th>
              <th>Placement</th>
            </tr>
          </thead>
          <tbody>
            ${studentList.map(s => `
              <tr>
                <td><code>${s.student_id || s.id || 'STU'}</code></td>
                <td><strong>${escapeHTML(s.name || 'Student')}</strong></td>
                <td>${escapeHTML(s.department || s.dept || 'Engineering')}</td>
                <td>Year ${s.year || 4}</td>
                <td><span class="cgpa-badge">${s.cgpa || 'N/A'}</span></td>
                <td><span class="placement-pill">${escapeHTML(s.placement_status || s.placement || 'Active')}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  let queryBadge = '';
  if (queryStr) {
    queryBadge = `
      <div class="query-chip">
        <span>⚡ <strong>SQL:</strong> <code>${escapeHTML(queryStr)}</code></span>
        <span style="font-size: 11px; color: #94a3b8;">${data.latency_ms || 120}ms</span>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="avatar bot-avatar">🤖</div>
    <div class="message-bubble">
      <p>${escapeHTML(summaryText)}</p>
      ${queryBadge}
      ${studentTableHTML}
      <div class="message-meta">
        <span>✅ Executed successfully</span> &bull; 
        <span>Latency: ${data.latency_ms || 120}ms</span> &bull; 
        <span>${formatTime()}</span>
      </div>
    </div>
  `;

  container.appendChild(row);
  scrollToBottom();
}

function appendIncidentErrorResponse(query, details = null) {
  const container = document.getElementById('messages-container');
  const row = document.createElement('div');
  row.className = 'message-row assistant';

  row.innerHTML = `
    <div class="avatar bot-avatar" style="background: #ef4444;">🚨</div>
    <div class="message-bubble" style="border-color: #ef4444; background: rgba(239, 68, 68, 0.05);">
      <p style="color: #fca5a5; font-weight: 700;">⚠️ Backend Service Failure (HTTP 500)</p>
      <p style="font-size: 13px; color: #cbd5e1; margin-top: 4px;">
        Unable to execute query: "<em>${escapeHTML(query)}</em>". The database connection pool is currently exhausted.
      </p>
      <div class="incident-error-card">
        <div class="incident-error-header">
          <span>💥 Error Trace: sqlalchemy.exc.TimeoutError</span>
        </div>
        <div class="incident-error-log">
          [ERROR] student-api /chat: QueuePool limit of size 10 overflow 10 reached, connection timed out, timeout 5.00 (Background incident INC-2026-018 triggered)
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
          <span style="font-size: 11px; color: #f87171;">Multi-agent incident responder notified. Approval email sent.</span>
          <button class="banner-action-btn" onclick="switchView('devops')">
            Open DevOps Approval Portal &rarr;
          </button>
        </div>
      </div>
      <div class="message-meta" style="color: #f87171;">
        <span>Incident INC-2026-018</span> &bull; <span>${formatTime()}</span>
      </div>
    </div>
  `;

  container.appendChild(row);
  scrollToBottom();
}

// Incident Management & Simulation
function simulateIncident() {
  CONFIG.activeIncident = true;
  triggerIncidentMode("Database Connection Pool Exhausted");
  
  // Also push a failure query to the chat for immediate visual feedback
  const input = document.getElementById('user-input');
  input.value = "Show students with CGPA above 8.5";
  handleChatSubmit(new Event('submit'));
}
window.simulateIncident = simulateIncident;

function triggerIncidentMode(reason) {
  CONFIG.activeIncident = true;
  updateStatusBadge(true);

  // Show banner
  document.getElementById('incident-banner').classList.remove('hidden');

  // Update Portal Metrics
  document.getElementById('stat-connections').textContent = '100 / 100';
  document.getElementById('stat-connections').className = 'stat-val alert';
  document.getElementById('stat-latency').textContent = '4,850 ms';
  document.getElementById('stat-latency').className = 'stat-val alert';
  document.getElementById('stat-error-rate').textContent = '63.2%';
  document.getElementById('stat-error-rate').className = 'stat-val alert';
  document.getElementById('stat-health').textContent = 'DEGRADED';
  document.getElementById('stat-health').className = 'stat-val alert';
  document.getElementById('incident-status-tag').textContent = 'INCIDENT ACTIVE';
  document.getElementById('incident-status-tag').style.color = '#ef4444';

  // Update timeline
  document.getElementById('tl-incident').style.display = 'block';
  document.getElementById('tl-analyzer').style.display = 'block';
  document.getElementById('tl-email').style.display = 'block';
  document.getElementById('tl-resolved').style.display = 'none';

  renderEmailPreview();
}

// DevOps Approval & Remediation Action
export async function approveIncidentAction() {
  const btn = document.getElementById('approve-action-btn');
  btn.disabled = true;
  btn.innerHTML = `<span>⏳</span> Executing allowlisted resolution tool...`;

  if (CONFIG.mode === 'live') {
    try {
      await fetch(`${CONFIG.backendUrl}/incidents/INC-2026-018/approve`, { method: 'POST' });
    } catch (e) {
      console.warn("Live approve call dispatched", e);
    }
  }

  // Simulate tool execution & recovery verification
  setTimeout(() => {
    btn.disabled = false;
    btn.innerHTML = `<span>✅</span> Approve Resolution Tool`;
    
    // Recovery metrics update
    CONFIG.activeIncident = false;
    updateStatusBadge(false);

    document.getElementById('incident-banner').classList.add('hidden');
    document.getElementById('stat-connections').textContent = '14 / 100';
    document.getElementById('stat-connections').className = 'stat-val recovered';
    document.getElementById('stat-latency').textContent = '180 ms';
    document.getElementById('stat-latency').className = 'stat-val recovered';
    document.getElementById('stat-error-rate').textContent = '0.0%';
    document.getElementById('stat-error-rate').className = 'stat-val recovered';
    document.getElementById('stat-health').textContent = 'HEALTHY';
    document.getElementById('stat-health').className = 'stat-val recovered';
    document.getElementById('incident-status-tag').textContent = 'RECOVERY VERIFIED';
    document.getElementById('incident-status-tag').style.color = '#10b981';

    // Show resolved timeline item
    document.getElementById('tl-resolved').style.display = 'block';

    // Add notification to chat
    appendRecoveryNotice();
    alert("✅ Resolution Approved!\n\nTool 'restart_student_api()' executed successfully.\nDatabase connections recycled: 100/100 -> 14/100.\nError rate dropped to 0.0%.\nService is now 100% HEALTHY!");
  }, 1200);
}
window.approveIncidentAction = approveIncidentAction;

export async function rejectIncidentAction() {
  if (CONFIG.mode === 'live') {
    try {
      await fetch(`${CONFIG.backendUrl}/incidents/INC-2026-018/reject`, { method: 'POST' });
    } catch (e) {
      console.warn("Live reject call dispatched", e);
    }
  }
  document.getElementById('incident-status-tag').textContent = 'REMEDIATION REJECTED';
  document.getElementById('incident-status-tag').style.color = '#f59e0b';
  alert("❌ Proposed resolution REJECTED by engineer.\n\nRemediation aborted. Incident remains open for manual escalation.");
}
window.rejectIncidentAction = rejectIncidentAction;

function resetIncident() {
  CONFIG.activeIncident = false;
  updateStatusBadge(false);
  document.getElementById('incident-banner').classList.add('hidden');
  document.getElementById('stat-connections').textContent = '14 / 100';
  document.getElementById('stat-connections').className = 'stat-val';
  document.getElementById('stat-latency').textContent = '180 ms';
  document.getElementById('stat-latency').className = 'stat-val';
  document.getElementById('stat-error-rate').textContent = '0.0%';
  document.getElementById('stat-error-rate').className = 'stat-val';
  document.getElementById('stat-health').textContent = 'HEALTHY';
  document.getElementById('stat-health').className = 'stat-val recovered';
  document.getElementById('incident-status-tag').textContent = 'SYSTEM STABLE';
  document.getElementById('incident-status-tag').style.color = '#10b981';

  document.getElementById('tl-incident').style.display = 'none';
  document.getElementById('tl-analyzer').style.display = 'none';
  document.getElementById('tl-email').style.display = 'none';
  document.getElementById('tl-resolved').style.display = 'none';
}
window.resetIncident = resetIncident;

function appendRecoveryNotice() {
  const container = document.getElementById('messages-container');
  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.innerHTML = `
    <div class="avatar bot-avatar">✅</div>
    <div class="message-bubble" style="border-color: #10b981; background: rgba(16, 185, 129, 0.08);">
      <p style="color: #34d399; font-weight: 700;">🟢 Incident Resolved &amp; Verified</p>
      <p style="font-size: 13px; color: #cbd5e1; margin-top: 4px;">
        DevOps approved action <code>restart_student_api()</code>. Connection pool refreshed (14/100 active).
        Service recovery verified across <code>/health</code> endpoints. Normal query execution resumed.
      </p>
      <div class="message-meta" style="color: #34d399;">
        <span>Verification Passed</span> &bull; <span>${formatTime()}</span>
      </div>
    </div>
  `;
  container.appendChild(row);
  scrollToBottom();
}

// System Status Badge Update
function updateStatusBadge(isIncident) {
  const badge = document.getElementById('system-status-badge');
  const text = document.getElementById('status-text');
  if (isIncident) {
    badge.className = 'status-badge incident';
    text.textContent = '🔴 System Status: Incident Detected';
  } else {
    badge.className = 'status-badge';
    text.textContent = '🟢 System Status: Healthy';
  }
}

// Background Health Poller (for Live Backend)
function startHealthPoller() {
  setInterval(async () => {
    if (CONFIG.mode === 'live') {
      try {
        const res = await fetch(`${CONFIG.backendUrl}/health`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          if (CONFIG.activeIncident) {
            CONFIG.activeIncident = false;
            updateStatusBadge(false);
          }
        } else {
          if (!CONFIG.activeIncident) {
            triggerIncidentMode('Backend returned unhealthy status');
          }
        }
      } catch (e) {
        // Only trigger if we were healthy
        if (!CONFIG.activeIncident) {
          triggerIncidentMode('Backend connection failed');
        }
      }
    }
  }, CONFIG.pollInterval * 1000);
}

// Render HTML Email Template into Preview Frame
function renderEmailPreview() {
  const container = document.getElementById('email-preview-content');
  if (!container) return;

  const incidentData = {
    incident_id: "INC-2026-018",
    severity: "HIGH",
    service: "Student Query API (student-api)",
    what_happened: "Backend failed with 500 error while handling student query requests. Connection pool reached saturation limit.",
    log_summary: "[ERROR] 2026-10-07T13:41:12Z student-api: QueuePool limit of size 10 overflow 10 reached, connection timed out, timeout 5.00s",
    root_cause: "Database Connection Pool Exhaustion",
    confidence: "94%",
    proposed_remediation: "restart_student_api()",
    risk: "LOW",
    blast_radius: "Student Query API container only (Database data untouched)",
    timestamp: "2026-10-07 13:41:18 UTC"
  };

  container.innerHTML = `
    <div style="background-color: #1e293b; border-radius: 12px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
      <div style="background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%); padding: 20px 24px;">
        <span style="display: inline-block; background-color: rgba(255, 255, 255, 0.2); color: #ffffff; font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; padding: 3px 8px; border-radius: 9999px; margin-bottom: 6px;">Automated AI Incident Response</span>
        <h2 style="margin: 0; font-size: 20px; font-weight: 800; color: #ffffff;">🚨 Incident Approval Required: ${incidentData.incident_id}</h2>
        <p style="margin: 4px 0 0 0; font-size: 12px; color: #fecaca;">Multi-agent investigation completed. Remediation proposal awaiting confirmation.</p>
      </div>

      <div style="padding: 24px;">
        <table style="width: 100%; border: 1px solid #334155; border-radius: 8px; background-color: #0f172a; margin-bottom: 20px; border-collapse: collapse;">
          <tr>
            <td style="padding: 10px 14px; font-size: 12px; border-bottom: 1px solid #1e293b; width: 50%;">
              <div style="color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase;">Service</div>
              <div style="color: #f1f5f9; font-weight: 600;">${incidentData.service}</div>
            </td>
            <td style="padding: 10px 14px; font-size: 12px; border-bottom: 1px solid #1e293b; width: 50%;">
              <div style="color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase;">Severity</div>
              <div><span style="background-color: #dc2626; color: #ffffff; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">${incidentData.severity}</span></div>
            </td>
          </tr>
          <tr>
            <td style="padding: 10px 14px; font-size: 12px;">
              <div style="color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase;">Time</div>
              <div style="color: #f1f5f9; font-weight: 600;">${incidentData.timestamp}</div>
            </td>
            <td style="padding: 10px 14px; font-size: 12px;">
              <div style="color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase;">Confidence</div>
              <div style="color: #34d399; font-weight: 700;">${incidentData.confidence} (High Consensus)</div>
            </td>
          </tr>
        </table>

        <div style="font-size: 12px; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 4px;">What Happened</div>
        <p style="font-size: 13px; color: #cbd5e1; margin: 0 0 16px 0;">${incidentData.what_happened}</p>

        <div style="font-size: 12px; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 4px;">Log Summary</div>
        <div style="background-color: #090d16; border: 1px solid #334155; border-left: 4px solid #ef4444; border-radius: 6px; padding: 10px 14px; font-family: monospace; font-size: 11px; color: #fca5a5; margin-bottom: 16px;">
          ${incidentData.log_summary}
        </div>

        <div style="font-size: 12px; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 4px;">Top 3 Hypotheses Generated</div>
        <div style="background-color: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin-bottom: 16px; font-size: 12px;">
          <div style="margin-bottom: 6px;"><span style="background: #1e293b; color: #94a3b8; padding: 2px 6px; border-radius: 4px; font-size: 10px;">H1</span> <strong>Database connection exhaustion</strong> — 75% probability</div>
          <div style="margin-bottom: 6px;"><span style="background: #1e293b; color: #94a3b8; padding: 2px 6px; border-radius: 4px; font-size: 10px;">H2</span> <strong>Database server overload</strong> — 15% probability</div>
          <div><span style="background: #1e293b; color: #94a3b8; padding: 2px 6px; border-radius: 4px; font-size: 10px;">H3</span> <strong>Backend API thread starvation</strong> — 10% probability</div>
        </div>

        <div style="font-size: 12px; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 4px;">Verification Evidence (Tool Calls)</div>
        <div style="margin-bottom: 16px; font-size: 11px; font-family: monospace;">
          <div style="background: #090d16; padding: 6px 10px; border-radius: 4px; color: #a7f3d0; border-left: 3px solid #10b981; margin-bottom: 4px;">✓ check_db_connections() &rarr; 100/100 active (EXHAUSTED)</div>
          <div style="background: #090d16; padding: 6px 10px; border-radius: 4px; color: #a7f3d0; border-left: 3px solid #10b981; margin-bottom: 4px;">✓ check_db_health() &rarr; DB container running, connections refused</div>
          <div style="background: #090d16; padding: 6px 10px; border-radius: 4px; color: #a7f3d0; border-left: 3px solid #10b981;">✓ check_backend_load() &rarr; CPU 12%, Memory 28% (Normal)</div>
        </div>

        <div style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.05) 100%); border: 1px solid #ef4444; border-radius: 8px; padding: 14px; margin-bottom: 16px;">
          <div style="font-size: 11px; font-weight: 700; color: #f87171; text-transform: uppercase;">Confirmed Root Cause</div>
          <h3 style="font-size: 15px; font-weight: 700; color: #ffffff; margin: 4px 0;">${incidentData.root_cause}</h3>
          <span style="background-color: #15803d; color: #dcfce7; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 9999px;">Confidence: ${incidentData.confidence}</span>
        </div>

        <div style="background-color: #0f172a; border: 1px solid #0284c7; border-left: 4px solid #0284c7; border-radius: 8px; padding: 14px; margin-bottom: 20px;">
          <div style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase;">Proposed Remediation Action</div>
          <div style="font-size: 14px; font-weight: 700; color: #f1f5f9; margin: 4px 0;">${incidentData.proposed_remediation}</div>
          <div style="font-size: 12px; color: #94a3b8;">
            Safety Check: <strong>PASSED</strong> &bull; Risk: <strong>${incidentData.risk}</strong> &bull; Blast Radius: <strong>${incidentData.blast_radius}</strong>
          </div>
        </div>

        <div style="background-color: #090d16; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center;">
          <p style="font-size: 12px; color: #94a3b8; margin: 0 0 12px 0;">
            ⚠️ <strong>Human-in-the-Loop Gate:</strong> Click below to approve execution on cloud infrastructure:
          </p>
          <div style="display: flex; justify-content: center; gap: 12px; flex-wrap: wrap;">
            <a href="decision-landing.html?action=approve&id=INC-2026-018" target="_blank" style="display: inline-block; text-decoration: none; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #ffffff; font-size: 13px; font-weight: 700; padding: 10px 20px; border-radius: 6px; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3);">
              ✅ APPROVE RESOLUTION
            </a>
            <a href="decision-landing.html?action=reject&id=INC-2026-018" target="_blank" style="display: inline-block; text-decoration: none; background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); color: #ffffff; font-size: 13px; font-weight: 700; padding: 10px 18px; border-radius: 6px; box-shadow: 0 4px 10px rgba(220, 38, 38, 0.3);">
              ❌ REJECT RESOLUTION
            </a>
          </div>
          <div style="margin-top: 10px;">
            <a href="decision-landing.html?action=approve&id=INC-2026-018" target="_blank" style="font-size: 11px; color: #38bdf8; text-decoration: underline;">
              ↗ Open Decision Landing &amp; Live Recovery Progress Page
            </a>
          </div>
        </div>

      </div>
    </div>
  `;
}

// Configuration Modal Handlers
function openConfigModal() {
  document.getElementById('config-modal').classList.remove('hidden');
}
window.openConfigModal = openConfigModal;

function closeConfigModal() {
  document.getElementById('config-modal').classList.add('hidden');
}
window.closeConfigModal = closeConfigModal;

function saveConfig() {
  const mode = document.getElementById('config-mode').value;
  const url = document.getElementById('config-backend-url').value.trim();
  const poll = document.getElementById('config-poll-interval').value;

  CONFIG.mode = mode;
  CONFIG.backendUrl = url;
  CONFIG.pollInterval = parseInt(poll, 10);

  localStorage.setItem('app_mode', mode);
  localStorage.setItem('backend_url', url);
  localStorage.setItem('poll_interval', poll);

  initUI();
  closeConfigModal();
}
window.saveConfig = saveConfig;

// Utilities
function scrollToBottom() {
  const container = document.getElementById('messages-container');
  container.scrollTop = container.scrollHeight;
}

function formatTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHTML(str) {
  return String(str).replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}

