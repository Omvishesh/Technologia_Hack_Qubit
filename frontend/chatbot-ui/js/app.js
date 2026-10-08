// Campus AI Assistant — chat client for the student-api backend (POST /chat, GET /health).

const stored = (key) => { try { return localStorage.getItem(key); } catch (e) { return null; } };

// Services run on the same host as this page: localhost in dev, the VM's address when deployed.
const PAGE_HOST = location.hostname || 'localhost';
const IS_LOCAL_PAGE = ['localhost', '127.0.0.1'].includes(PAGE_HOST);
const defaultUrl = (port) => `${location.protocol === 'https:' ? 'https:' : 'http:'}//${PAGE_HOST}:${port}`;
// A saved localhost URL only makes sense when the page itself is local (older builds saved it by default).
const storedUrl = (key) => {
  const url = stored(key);
  return url && !IS_LOCAL_PAGE && /\/\/(localhost|127\.0\.0\.1)[:/]/.test(url) ? null : url;
};

const CONFIG = {
  mode: stored('app_mode') || 'live', // 'live' or 'demo'
  backendUrl: (storedUrl('backend_url') || defaultUrl(8000)).replace(/\/+$/, ''),
  incidentUrl: (storedUrl('incident_url') || defaultUrl(8001)).replace(/\/+$/, ''),
  pollInterval: parseInt(stored('poll_interval') || '5', 10),
};

const $ = (id) => document.getElementById(id);
const els = {};
let pollTimer = null;
let busy = false;
let tracker = null;          // live view of the incident-response pipeline for the current outage
let lastFailedQuery = '';

document.addEventListener('DOMContentLoaded', () => {
  ['main', 'messages', 'typing', 'chat-scroll', 'chat-form', 'user-input', 'send-btn', 'sidebar',
   'status-box', 'status-dot', 'status-label', 'nav-docs', 'config-modal',
   'config-mode', 'config-backend-url', 'config-incident-url', 'config-poll-interval'].forEach(id => { els[id] = $(id); });

  // "Ask again" button shown once an incident is resolved
  els.messages.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-retry]');
    if (!btn || busy) return;
    els['user-input'].value = btn.dataset.retry;
    updateSendState();
    els['chat-form'].requestSubmit();
  });

  const input = els['user-input'];
  input.addEventListener('input', () => { autoGrow(); updateSendState(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      els['chat-form'].requestSubmit();
    }
  });
  els['chat-form'].addEventListener('submit', handleSubmit);

  $('menu-btn').addEventListener('click', () => els.sidebar.classList.toggle('expanded'));
  $('nav-chat').addEventListener('click', () => input.focus());
  $('nav-new').addEventListener('click', newChat);
  $('nav-settings').addEventListener('click', openSettings);
  $('config-cancel').addEventListener('click', closeSettings);
  $('config-save').addEventListener('click', saveSettings);
  els['config-modal'].addEventListener('click', (e) => { if (e.target === els['config-modal']) closeSettings(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSettings(); });

  applyConfig();
  input.focus();
});

// ── Chat ─────────────────────────────────────────────────

async function handleSubmit(e) {
  e.preventDefault();
  const input = els['user-input'];
  const query = input.value.trim();
  if (!query || busy) return;

  setChatMode(true);
  appendUserMessage(query);
  input.value = '';
  autoGrow();
  setBusy(true);

  try {
    if (CONFIG.mode === 'demo') {
      await new Promise(r => setTimeout(r, 600));
      appendBotResponse(getMockData(query));
      return;
    }

    const res = await fetch(`${CONFIG.backendUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
      signal: AbortSignal.timeout(30000),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      appendBotResponse(data);
    } else {
      data.http_status = res.status;
      appendErrorResponse(data);
      if (res.status >= 500) {
        setStatus('incident', data.message || `HTTP ${res.status}`);
        lastFailedQuery = query;
        startIncidentTracking();
      }
    }
  } catch (err) {
    const timedOut = err && err.name === 'TimeoutError';
    appendErrorResponse({ error: timedOut ? 'The backend did not respond within 30 seconds.' : `Could not reach ${CONFIG.backendUrl}. Is the backend running?` });
    setStatus('offline', 'Backend unreachable');
  } finally {
    setBusy(false);
  }
}

function getMockData(query) {
  if (typeof window.getMockResponse === 'function') return window.getMockResponse(query);
  return { summary: `Demo mode: no mock data for "${query}".`, students: [] };
}

function newChat() {
  stopIncidentTracking();
  els.messages.innerHTML = '';
  setChatMode(false);
  els['user-input'].value = '';
  autoGrow();
  updateSendState();
  els['user-input'].focus();
}

// ── Message rendering ────────────────────────────────────

function appendUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'msg user';
  row.innerHTML = `<div class="bubble">${escapeHTML(text)}</div>`;
  pushMessage(row);
}

function appendBotResponse(data) {
  // Live backend: { response, data, metadata: { generated_sql, row_count, latency_ms } }.
  // Mock data:    { summary, students, query (SQL), latency_ms }.
  const meta = data.metadata || {};
  const rows = data.data || data.students || data.results || [];
  const answer = data.response || data.summary || data.message || 'Here are the matching records.';
  const sql = meta.generated_sql || data.sql || (data.metadata ? null : data.query) || null;
  const latency = meta.latency_ms ?? data.latency_ms;

  // Natural-language answer first, then the results table, then the SQL (collapsed).
  const isScalar = rows.length === 1 && Object.keys(rows[0]).length === 1; // e.g. COUNT(*) — the answer says it
  const table = rows.length && !isScalar ? renderRowsTable(rows) : '';

  const stats = [`${rows.length} row${rows.length === 1 ? '' : 's'}`];
  if (latency != null) stats.push(`${Math.round(latency).toLocaleString()} ms`);
  const sqlDetails = sql ? `
      <details class="details">
        <summary><span class="sql-tag">SQL</span> · ${stats.join(' · ')}</summary>
        <div class="inner"><div class="sql-block">${escapeHTML(sql)}</div></div>
      </details>` : '';

  const row = document.createElement('div');
  row.className = 'msg bot';
  row.innerHTML = `
    <span class="mini-ring" aria-hidden="true"></span>
    <div class="body">
      <div class="answer">${renderMarkdown(answer)}</div>
      ${table}
      ${sqlDetails}
      <div class="meta">${formatTime()}${sql ? '' : ' · ' + stats.join(' · ')}</div>
    </div>`;
  pushMessage(row);
}

function appendErrorResponse(details) {
  // Backend errors: { error_code, message, request_id, http_status }; network errors: { error }.
  const title = details.http_status
    ? (details.http_status >= 500 ? 'The student service is having trouble' : 'Request could not be processed')
    : 'Backend unreachable';
  const text = details.message || details.detail || details.error || 'Something went wrong.';
  const code = details.error_code
    ? `${details.error_code}${details.request_id ? ' · ' + details.request_id : ''}${details.http_status ? ' · HTTP ' + details.http_status : ''}`
    : '';

  const row = document.createElement('div');
  row.className = 'msg bot error';
  row.innerHTML = `
    <span class="mini-ring" aria-hidden="true"></span>
    <div class="body">
      <div class="err-title">${escapeHTML(title)}</div>
      <div class="err-text">${escapeHTML(typeof text === 'string' ? text : JSON.stringify(text))}</div>
      ${code ? `<div class="err-code">${escapeHTML(code)}</div>` : ''}
    </div>`;
  pushMessage(row);
}

function pushMessage(row) {
  els.messages.appendChild(row);
  scrollToBottom();
}

function renderRowsTable(rows) {
  const isStudent = 'name' in rows[0];
  const cols = isStudent
    ? ['name', 'department', 'year', 'cgpa', 'skills', 'placement_status'].filter(c => c in rows[0])
    : Object.keys(rows[0]);
  const label = (c) => ({ student_id: 'ID', placement_status: 'Placement', cgpa: 'CGPA' }[c] || c.replace(/_/g, ' '));
  const placementClass = (v) => ({ 'Placed': 'placed', 'Eligible': 'eligible' }[v] || 'not-eligible');
  const cell = (c, v) => {
    const cls = c === 'name' ? 'name' : c === 'cgpa' ? 'cgpa' : c === 'skills' ? 'skills'
      : c === 'placement_status' ? `placement ${placementClass(v)}` : '';
    const text = Array.isArray(v) ? v.join(', ') : c === 'cgpa' && typeof v === 'number' ? v.toFixed(2) : (v ?? '');
    return `<td${cls ? ` class="${cls}"` : ''}>${escapeHTML(text)}</td>`;
  };
  return `
    <div class="table-wrap results">
      <table>
        <thead><tr>${cols.map(c => `<th>${escapeHTML(label(c))}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(r => `<tr>${cols.map(c => cell(c, r[c])).join('')}</tr>`).join('')}</tbody>
      </table>
    </div>`;
}

// Minimal Markdown for LLM answers (paragraphs, headings, bullets, tables, bold/italic/code).
// Escapes first, so model output can never inject HTML.
function renderMarkdown(md) {
  const inline = (s) => escapeHTML(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
  const cells = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
  const lines = String(md).split('\n');
  const out = [];
  let list = null; // consecutive bullet / numbered lines, grouped into one <ul>/<ol>
  const flushList = () => {
    if (list) out.push(`<${list.tag}>${list.items.join('')}</${list.tag}>`);
    list = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    const next = (lines[i + 1] || '').trim();
    const item = lines[i].match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
    if (item) {
      if (!list) list = { tag: /\d/.test(item[2]) ? 'ol' : 'ul', items: [] };
      list.items.push(`<li${item[1].length >= 2 ? ' class="sub"' : ''}>${inline(item[3])}</li>`);
      continue;
    }
    if (!line) continue; // blank lines between list items shouldn't split the list
    flushList();
    if (line.startsWith('|') && /^\|?\s*:?-{3,}/.test(next)) {
      const head = cells(line);
      const rows = [];
      i += 1; // skip the |---| separator
      while (i + 1 < lines.length && lines[i + 1].trim().startsWith('|')) rows.push(cells(lines[++i]));
      out.push(`<div class="table-wrap"><table><thead><tr>${head.map(h => `<th>${inline(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
    } else if (/^#{1,6}\s+/.test(line)) {
      out.push(`<p><strong>${inline(line.replace(/^#{1,6}\s+/, ''))}</strong></p>`);
    } else {
      out.push(`<p>${inline(line)}</p>`);
    }
  }
  flushList();
  return out.join('');
}

// ── Incident pipeline (incident-response service) ────────

const PIPELINE = ['detected', 'analyzing', 'hypotheses_generated', 'verifying', 'root_cause_confirmed',
  'remediation_proposed', 'safety_checked', 'awaiting_approval', 'approved', 'resolving', 'resolved'];
const TERMINAL = ['resolved', 'rejected', 'recovery_failed'];
const STAGE_TEXT = {
  detected: 'Incident opened',
  analyzing: 'Collecting logs and metrics, analysing errors…',
  hypotheses_generated: 'Generated root-cause hypotheses…',
  verifying: 'Running verification tools against the backend…',
};

function startIncidentTracking() {
  if (CONFIG.mode !== 'live' || tracker) return;
  const el = document.createElement('div');
  el.className = 'msg bot';
  tracker = { el, id: null, status: null, startedAt: Date.now(), failures: 0, timer: null };
  pushMessage(el);
  renderTracker(null);
  pollIncident();
  tracker.timer = setInterval(pollIncident, 3000);
}

function stopIncidentTracking() {
  if (tracker) clearInterval(tracker.timer);
  tracker = null;
}

async function pollIncident() {
  const t = tracker;
  if (!t) return;
  try {
    if (!t.id) {
      const res = await fetch(`${CONFIG.incidentUrl}/incidents`, { signal: AbortSignal.timeout(3000) });
      const { incidents = [] } = await res.json(); // newest first
      // An outage that's still open, else one opened around the time this request failed.
      const inc = incidents.find(i => !TERMINAL.includes(i.status))
        || incidents.find(i => Date.parse(i.created_at) >= t.startedAt - 60000);
      if (!inc) {
        if (Date.now() - t.startedAt > 90000) finishTracking('missing');
        return;
      }
      t.id = inc.id;
    }
    const res = await fetch(`${CONFIG.incidentUrl}/incidents/${encodeURIComponent(t.id)}`, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const inc = await res.json();
    t.failures = 0;
    t.inc = inc;
    if (inc.status !== t.status) {
      t.status = inc.status;
      renderTracker(inc);
    }
    if (TERMINAL.includes(inc.status)) finishTracking(inc.status, inc);
  } catch (e) {
    t.failures += 1;
    if (t.failures === 3) renderTracker(t.inc || null, `Can't reach the incident service at ${CONFIG.incidentUrl} — still retrying…`);
    if (!t.id && Date.now() - t.startedAt > 90000) finishTracking('missing');
  }
}

function finishTracking(outcome, inc) {
  const t = tracker;
  stopIncidentTracking();
  if (outcome === 'missing') {
    renderTracker(null, `No incident was raised. Is the incident service running at ${CONFIG.incidentUrl}?`, t);
  } else if (outcome === 'resolved') {
    pollHealth();
  }
}

function renderTracker(inc, note, t = tracker) {
  if (!t) return;
  const status = inc ? inc.status : null;
  const at = PIPELINE.indexOf(status);
  const cause = inc && inc.root_cause && inc.root_cause.cause;
  const confidence = inc && inc.root_cause ? Math.round(inc.root_cause.confidence * 100) : null;
  const action = inc && inc.remediation && inc.remediation.action;
  const phoned = inc && (inc.timeline || []).some(e => e.stage === 'phone' && /sent/i.test(e.description));

  // [title, detail, state] — state: done | active | pending | failed
  const steps = [
    ['Incident detected', inc ? `${inc.id} · ${inc.error_message || inc.error_code || ''}` : 'Notifying the incident response system…',
      inc ? 'done' : 'active'],
    ['AI agents investigating', at >= 4 ? 'Logs analysed, hypotheses verified with backend tools' : (STAGE_TEXT[status] || ''),
      at >= 4 ? 'done' : inc ? 'active' : 'pending'],
    ['Root cause identified', cause ? `${cause}${confidence != null ? ` · ${confidence}% confidence` : ''}` : '',
      cause && at >= 4 ? 'done' : 'pending'],
    ['DevOps approval', status === 'rejected' ? 'The engineer rejected the automated fix — manual investigation needed'
      : status === 'resolved' && !inc.approved_by ? 'Not needed — the service recovered on its own'
      : at === 7 ? `Fix proposed: ${action || 'remediation'} · approval email sent${phoned ? ' · 📱 phone alerted' : ''}`
      : at >= 8 || status === 'recovery_failed' ? `Approved: ${action || 'remediation'}`
      : at >= 4 ? 'Preparing fix and running safety checks…' : '',
      status === 'rejected' ? 'failed' : at >= 8 || status === 'recovery_failed' ? 'done' : at >= 4 ? 'active' : 'pending'],
    ['Fix applied & recovery verified', status === 'resolved' ? ((inc.recovery && inc.recovery.details) || 'Service restored')
      : status === 'recovery_failed' ? 'Recovery could not be verified — escalated'
      : at >= 8 ? 'Applying the fix and checking service health…' : '',
      status === 'resolved' ? 'done' : status === 'recovery_failed' ? 'failed' : at >= 8 ? 'active' : 'pending'],
  ];

  const title = status === 'resolved' ? 'Service restored'
    : status === 'rejected' || status === 'recovery_failed' ? 'Incident needs manual attention'
    : 'Incident response in progress';
  const tone = status === 'resolved' ? 'ok' : status === 'rejected' || status === 'recovery_failed' ? 'bad' : '';
  const retry = status === 'resolved' && lastFailedQuery
    ? `<button type="button" class="retry-btn" data-retry="${escapeHTML(lastFailedQuery)}">Ask again: “${escapeHTML(lastFailedQuery)}”</button>` : '';

  t.el.innerHTML = `
    <span class="mini-ring" aria-hidden="true"></span>
    <div class="body">
      <div class="tracker ${tone}">
        <div class="tracker-head">
          <span class="tracker-title">${title}</span>
          ${inc ? `<span class="tracker-id">${escapeHTML(inc.id)}</span>` : ''}
        </div>
        <ol class="steps">
          ${steps.map(([name, detail, state]) => `
            <li class="step ${state}">
              <span class="step-dot"></span>
              <div>
                <div class="step-title">${escapeHTML(name)}</div>
                ${detail ? `<div class="step-detail">${escapeHTML(detail)}</div>` : ''}
              </div>
            </li>`).join('')}
        </ol>
        ${note ? `<div class="tracker-note">${escapeHTML(note)}</div>` : ''}
        ${retry}
      </div>
    </div>`;
  scrollToBottom();
}

// ── Backend health ───────────────────────────────────────

async function pollHealth() {
  if (CONFIG.mode !== 'live') return;
  try {
    const res = await fetch(`${CONFIG.backendUrl}/health`, { signal: AbortSignal.timeout(3000) });
    // /health answers 200 even when the pool is exhausted; the verdict is in `status`.
    const body = await res.json().catch(() => ({}));
    if (res.ok && body.status === 'healthy') {
      setStatus('healthy', 'Live API · healthy');
    } else {
      setStatus('incident', (body.database && body.database.error) || `Backend status: ${body.status || res.status}`);
    }
  } catch (e) {
    setStatus('offline', 'Backend unreachable');
  }
}

function setStatus(state, text) {
  els['status-dot'].className = `status-dot ${state === 'offline' ? 'incident' : state}`;
  const label = {
    healthy: 'System healthy',
    incident: 'Incident detected',
    offline: 'Backend offline',
    demo: 'Demo mode',
  }[state] || text;
  els['status-label'].textContent = label;
  els['status-box'].title = `${label} — ${text}`;
}

// ── Settings ─────────────────────────────────────────────

function applyConfig() {
  els['nav-docs'].href = `${CONFIG.backendUrl}/docs`;
  clearInterval(pollTimer);
  if (CONFIG.mode === 'live') {
    setStatus('unknown', 'Checking backend…');
    pollHealth();
    pollTimer = setInterval(pollHealth, CONFIG.pollInterval * 1000);
  } else {
    setStatus('demo', 'Offline mock data — no backend calls');
  }
}

function openSettings() {
  els['config-mode'].value = CONFIG.mode;
  els['config-backend-url'].value = CONFIG.backendUrl;
  els['config-incident-url'].value = CONFIG.incidentUrl;
  els['config-poll-interval'].value = CONFIG.pollInterval;
  els['config-modal'].hidden = false;
}

function closeSettings() {
  els['config-modal'].hidden = true;
}

function saveSettings() {
  CONFIG.mode = els['config-mode'].value;
  CONFIG.backendUrl = (els['config-backend-url'].value.trim() || defaultUrl(8000)).replace(/\/+$/, '');
  CONFIG.incidentUrl = (els['config-incident-url'].value.trim() || defaultUrl(8001)).replace(/\/+$/, '');
  CONFIG.pollInterval = Math.max(2, parseInt(els['config-poll-interval'].value, 10) || 5);
  try {
    localStorage.setItem('app_mode', CONFIG.mode);
    localStorage.setItem('backend_url', CONFIG.backendUrl);
    localStorage.setItem('incident_url', CONFIG.incidentUrl);
    localStorage.setItem('poll_interval', String(CONFIG.pollInterval));
  } catch (e) { /* storage unavailable — settings last for this session only */ }
  applyConfig();
  closeSettings();
}

// ── UI helpers ───────────────────────────────────────────

function setChatMode(on) {
  els.main.classList.toggle('empty', !on);
}

function setBusy(on) {
  busy = on;
  els.typing.hidden = !on;
  updateSendState();
  if (on) scrollToBottom();
}

function updateSendState() {
  els['send-btn'].disabled = busy || !els['user-input'].value.trim();
}

function autoGrow() {
  const t = els['user-input'];
  t.style.height = 'auto';
  t.style.height = `${Math.min(t.scrollHeight, 200)}px`;
}

function scrollToBottom() {
  const s = els['chat-scroll'];
  requestAnimationFrame(() => { s.scrollTop = s.scrollHeight; });
}

function formatTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHTML(str) {
  return String(str).replace(/[&<>'"]/g,
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}
