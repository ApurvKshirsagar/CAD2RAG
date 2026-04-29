const API = 'http://127.0.0.1:8000/api';
const MAX_FILES = 5;

let state = {
  sessionId: null,
  fileType: 'dxf',
  queue: [],
  loading: false,
  hasPDF: false,
  rules: [],
  lastReportId: null,
};

// ─── File type toggle ─────────────────────────────────────────────
function setFileType(type) {
  state.fileType = type;
  document.getElementById('btn-dxf').classList.toggle('active', type === 'dxf');
  document.getElementById('btn-pdf').classList.toggle('active', type === 'pdf');
  document.getElementById('fileTypeLabel').textContent = type.toUpperCase();
  document.getElementById('fileInput').accept =
    type === 'dxf' ? '.dxf' : '.pdf';
}

// ─── Drag & drop ──────────────────────────────────────────────────
function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.add('drag-over');
}
function handleDragLeave() {
  document.getElementById('dropZone').classList.remove('drag-over');
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.remove('drag-over');
  Array.from(e.dataTransfer.files).forEach(addFileToQueue);
}
function handleFileSelect(e) {
  Array.from(e.target.files).forEach(addFileToQueue);
  e.target.value = '';
}

// ─── Queue ────────────────────────────────────────────────────────
function addFileToQueue(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (ext !== state.fileType) {
    showBannerError(`"${file.name}" is not a .${state.fileType} file.`);
    return;
  }
  if (state.queue.length >= MAX_FILES) {
    showBannerError(`Maximum ${MAX_FILES} files per session.`);
    return;
  }
  if (state.queue.find((q) => q.name === file.name)) {
    showBannerError(`"${file.name}" already in queue.`);
    return;
  }
  state.queue.push({
    file,
    name: file.name,
    ext,
    status: 'pending',
    summary: null,
  });
  renderQueue();
}
function removeFromQueue(idx) {
  state.queue.splice(idx, 1);
  renderQueue();
}

function renderQueue() {
  const container = document.getElementById('fileQueue');
  const processBtn = document.getElementById('processAllBtn');
  const slotsEl = document.getElementById('slotsLeft');

  const remaining = MAX_FILES - state.queue.length;
  if (slotsEl) {
    slotsEl.textContent =
      remaining > 0
        ? `${remaining} slot${remaining > 1 ? 's' : ''} remaining`
        : 'Session full';
  }

  if (state.queue.length === 0) {
    if (container) container.innerHTML = '';
    if (processBtn) processBtn.style.display = 'none';
    return;
  }

  const pendingCount = state.queue.filter((q) => q.status === 'pending').length;
  const doneCount = state.queue.filter((q) => q.status === 'done').length;

  if (processBtn) {
    processBtn.style.display = 'block';
    processBtn.disabled = pendingCount === 0 || state.loading;
    processBtn.textContent = state.loading
      ? 'Processing…'
      : doneCount > 0 && pendingCount > 0
      ? `Process ${pendingCount} More`
      : pendingCount === 0
      ? 'All Processed'
      : `Process ${pendingCount} File${pendingCount > 1 ? 's' : ''}`;
  }

  if (!container) return;
  const ICON = {
    pending: '⏳',
    processing: '<span class="spinner"></span>',
    done: '✅',
    error: '❌',
  };
  container.innerHTML = state.queue
    .map((item, idx) => {
      const s = item.status || 'pending';
      const summary = item.summary
        ? `<div class="q-summary">${
            item.ext === 'dxf'
              ? `Layers: ${item.summary.layers} · Entities: ${item.summary.entities}`
              : `Pages: ${item.summary.total_pages}`
          }</div>`
        : '';
      const del =
        s !== 'processing'
          ? `<button class="q-remove" onclick="removeFromQueue(${idx})" title="Remove">✕</button>`
          : '';
      return `<div class="queue-item status-${s}">
      <div class="q-icon">${ICON[s] || '⏳'}</div>
      <div class="q-info"><div class="q-name">${escHtml(
        item.name
      )}</div>${summary}</div>
      ${del}
    </div>`;
    })
    .join('');
}

// ─── Process ──────────────────────────────────────────────────────
async function processAll() {
  if (state.loading) return;
  state.loading = true;
  renderQueue();

  if (!state.sessionId) {
    try {
      const res = await fetch(`${API}/session`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not create session');
      state.sessionId = data.session_id;
    } catch (err) {
      showBannerError(`Session error: ${err.message}`);
      state.loading = false;
      renderQueue();
      return;
    }
  }

  for (const item of state.queue.filter((q) => q.status === 'pending')) {
    item.status = 'processing';
    renderQueue();
    const fd = new FormData();
    fd.append('file', item.file);
    try {
      const res = await fetch(
        `${API}/upload?session_id=${encodeURIComponent(state.sessionId)}`,
        { method: 'POST', body: fd }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      item.status = 'done';
      item.summary = data.summary;
      item.fileId = data.file_id;
    } catch (err) {
      item.status = 'error';
      item.errorMsg = err.message;
    }
    renderQueue();
  }

  state.loading = false;
  renderQueue();
  const doneFiles = state.queue.filter((q) => q.status === 'done');
  if (doneFiles.length > 0) activateChat(doneFiles);
}

// ─── Activate chat ────────────────────────────────────────────────
function activateChat(doneFiles) {
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('chatArea').style.display = 'flex';
  document.getElementById('inputBar').style.display = 'block';
  document.getElementById('toolbar').style.display = 'flex';
  updateSessionPanel();

  const pdfFiles = doneFiles.filter((f) => f.ext === 'pdf');
  if (pdfFiles.length > 0) {
    state.hasPDF = true;
    document.getElementById('complianceTriggerBtn').style.display = 'flex';
    updateDrawerScope(pdfFiles);
  }

  const tFiles = document.getElementById('toolbarFiles');
  if (tFiles) {
    tFiles.textContent =
      doneFiles.length > 1
        ? `${doneFiles.length} files · ${doneFiles
            .map((f) => f.name)
            .join(', ')}`
        : doneFiles[0].name;
  }

  const welcome =
    doneFiles.length > 1
      ? `${doneFiles.length} files loaded.\n\n📂 ${doneFiles
          .map((f) => f.name)
          .join(
            ', '
          )}\n\nAsk questions across all files, or use the Compliance Check button above to audit your PDFs.`
      : buildSingleWelcome(doneFiles[0]);
  appendMessage('assistant', welcome);
}

function buildSingleWelcome(item) {
  const s = item.summary;
  if (item.ext === 'dxf')
    return `DXF loaded.\n\n📐 ${item.name}\n🗂 Layers: ${s.layers}\n🔷 Entities: ${s.entities}\n\nAsk me anything about this drawing.`;
  return `PDF loaded.\n\n📄 ${item.name}\n📖 Pages: ${s.total_pages}\n\nAsk questions about this document, or click "Compliance Check" above to audit it against a rule set.`;
}

function updateSessionPanel() {
  document.getElementById('sessionPanel').style.display = 'block';
  const doneFiles = state.queue.filter((q) => q.status === 'done');
  let html = `<strong>Files loaded:</strong> ${doneFiles.length}<br>`;
  doneFiles.forEach((f) => {
    html += `<div class="session-file"><span class="sf-name">${escHtml(
      f.name
    )}</span><span class="sf-type">${f.ext.toUpperCase()}</span></div>`;
  });
  document.getElementById('sessionInfo').innerHTML = html;
}

// ─── Chat query ───────────────────────────────────────────────────
async function sendQuery() {
  const input = document.getElementById('questionInput');
  const question = input.value.trim();
  if (!question || state.loading || !state.sessionId) return;

  state.loading = true;
  input.value = '';
  autoResize(input);
  document.getElementById('sendBtn').disabled = true;
  appendMessage('user', question);
  const typingId = addTyping();

  try {
    const res = await fetch(`${API}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.sessionId, question }),
    });
    const data = await res.json();
    removeTyping(typingId);
    if (!res.ok) throw new Error(data.detail || 'Query failed');
    appendMessage('assistant', data.answer, false, data.files_queried);
  } catch (err) {
    removeTyping(typingId);
    appendMessage('assistant', `Error: ${err.message}`, true);
  } finally {
    state.loading = false;
    document.getElementById('sendBtn').disabled = false;
    input.focus();
  }
}

// ─── Compliance drawer ────────────────────────────────────────────
function openComplianceDrawer() {
  document.getElementById('drawerBackdrop').classList.add('open');
  document.getElementById('complianceDrawer').classList.add('open');
  setTimeout(() => document.getElementById('cmRuleInput')?.focus(), 280);
}

function closeComplianceDrawer() {
  document.getElementById('drawerBackdrop').classList.remove('open');
  document.getElementById('complianceDrawer').classList.remove('open');
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeComplianceDrawer();
});

function updateDrawerScope(pdfFiles) {
  const el = document.getElementById('dfScope');
  if (!el) return;
  const names = pdfFiles.map((f) => f.name).join(', ');
  el.innerHTML = `<strong>Scope:</strong> ${escHtml(names)}`;
}

// ─── Rules ────────────────────────────────────────────────────────
function handleRuleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    addRuleFromInput();
  }
}

function addRuleFromInput() {
  const input = document.getElementById('cmRuleInput');
  if (!input) return;
  const lines = input.value
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean);
  lines.forEach(addRule);
  input.value = '';
  // Auto-resize textarea back
  input.style.height = 'auto';
}

function addRule(text) {
  if (!text || state.rules.includes(text)) return;
  state.rules.push(text);
  renderRuleList();
}

function removeRule(idx) {
  state.rules.splice(idx, 1);
  renderRuleList();
}

function clearAllRules() {
  if (state.rules.length === 0) return;
  if (!confirm(`Clear all ${state.rules.length} rules?`)) return;
  state.rules = [];
  renderRuleList();
}

function importRules(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    let added = 0;
    ev.target.result
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
      .forEach((line) => {
        if (!state.rules.includes(line)) {
          state.rules.push(line);
          added++;
        }
      });
    renderRuleList();
    showBannerError(
      `Imported ${added} rule${added !== 1 ? 's' : ''} successfully.`
    );
  };
  reader.readAsText(file);
  e.target.value = '';
}

function renderRuleList() {
  const list = document.getElementById('cmRuleList');
  const countEl = document.getElementById('cmRuleCount');
  const badge = document.getElementById('complianceBadge');
  const runBtn = document.getElementById('dfRunBtn');
  const subtitle = document.getElementById('drawerSubtitle');

  const n = state.rules.length;

  if (countEl) countEl.textContent = n;
  if (badge) {
    badge.textContent = n;
    badge.style.display = n > 0 ? 'inline-block' : 'none';
  }
  if (runBtn) runBtn.disabled = n === 0 || state.loading;
  if (subtitle)
    subtitle.textContent =
      n === 0 ? 'No rules added yet' : `${n} rule${n !== 1 ? 's' : ''} ready`;

  if (!list) return;

  if (n === 0) {
    list.innerHTML = `
      <div class="rule-empty-state">
        <div class="res-icon">📋</div>
        <div class="res-text">No rules yet</div>
        <div class="res-sub">Type a rule above or import a .txt file</div>
      </div>`;
    return;
  }

  list.innerHTML = state.rules
    .map(
      (rule, idx) => `
    <div class="rule-card">
      <span class="rule-card-num">${idx + 1}</span>
      <span class="rule-card-text">${escHtml(rule)}</span>
      <button class="rule-card-del" onclick="removeRule(${idx})" title="Remove rule">✕</button>
    </div>`
    )
    .join('');
}

// ─── Run compliance ───────────────────────────────────────────────
async function runComplianceCheck() {
  if (state.rules.length === 0 || state.loading || !state.sessionId) return;

  state.loading = true;
  const runBtn = document.getElementById('dfRunBtn');
  const runBtnText = document.getElementById('dfRunBtnText');
  if (runBtn) runBtn.disabled = true;
  if (runBtnText) runBtnText.textContent = 'Running…';
  document.getElementById('sendBtn').disabled = true;

  try {
    const res = await fetch(`${API}/compliance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.sessionId, rules: state.rules }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Compliance check failed');

    closeComplianceDrawer();
    setTimeout(() => {
      appendMessage(
        'user',
        `Compliance check · ${state.rules.length} rule${
          state.rules.length !== 1 ? 's' : ''
        }`
      );
      state.lastReportId = appendComplianceResult(data);
    }, 300);
  } catch (err) {
    showBannerError(`Compliance check failed: ${err.message}`);
  } finally {
    state.loading = false;
    if (runBtnText) runBtnText.textContent = 'Run Compliance Check';
    if (runBtn) runBtn.disabled = state.rules.length === 0;
    document.getElementById('sendBtn').disabled = false;
  }
}

// ─── Compliance result card ───────────────────────────────────────
// Global store so download functions can access any report by id
const _reports = {};

function appendComplianceResult(data) {
  const { total_rules, summary, results } = data;
  const messages = document.getElementById('messages');

  const id = 'report-' + Date.now();
  _reports[id] = data; // store for download

  const wrapper = document.createElement('div');
  wrapper.className = 'message assistant';
  wrapper.id = id;

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = 'CAD2RAG — Compliance Report';

  const card = document.createElement('div');
  card.className = 'compliance-card';

  // Sort: non_compliant first, then uncertain, then compliant
  const ORDER = { non_compliant: 0, uncertain: 1, compliant: 2 };
  const sorted = [...results].sort((a, b) => ORDER[a.status] - ORDER[b.status]);

  const filesLabel = state.queue
    .filter((q) => q.status === 'done' && q.ext === 'pdf')
    .map((f) => f.name)
    .join(', ');

  card.innerHTML = `
    <div class="cc-summary">
      <div class="cc-summary-top">
        <div class="cc-title">Compliance Report · ${total_rules} rule${
    total_rules !== 1 ? 's' : ''
  }</div>
        <div class="cc-dl-group">
          <div class="cc-dl-label">Download</div>
          <button class="cc-dl-btn" onclick="downloadReport('${id}','pdf-full')" title="PDF with explanations for each rule">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            PDF with explanations
          </button>
          <button class="cc-dl-btn" onclick="downloadReport('${id}','pdf-brief')" title="PDF with status only, no explanations">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            PDF without explanations
          </button>
        </div>
      </div>
      <div class="cc-pills">
        <span class="cc-pill compliant">✔ ${summary.compliant} Compliant</span>
        <span class="cc-pill uncertain">⚠ ${summary.uncertain} Uncertain</span>
        <span class="cc-pill non_compliant">✘ ${
          summary.non_compliant
        } Non-compliant</span>
      </div>
    </div>
    <div class="cc-rules">${sorted.map(buildRuleRow).join('')}</div>`;

  wrapper.appendChild(label);
  wrapper.appendChild(card);
  messages.appendChild(wrapper);
  document.getElementById('chatArea').scrollTop = 99999;
  return id;
}

// ─── Download report ──────────────────────────────────────────────
function downloadReport(reportId, format) {
  const data = _reports[reportId];
  if (!data) {
    showBannerError('Report data not found.');
    return;
  }

  const { total_rules, summary, results } = data;
  const ORDER = { non_compliant: 0, uncertain: 1, compliant: 2 };
  const sorted = [...results].sort((a, b) => ORDER[a.status] - ORDER[b.status]);
  const withExplanations = format === 'pdf-full';

  const filesLabel =
    state.queue
      .filter((q) => q.status === 'done' && q.ext === 'pdf')
      .map((f) => f.name)
      .join(', ') || 'PDF documents';
  const dateStr = new Date().toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  const STATUS_COLOR = {
    compliant: '#16a34a',
    uncertain: '#d97706',
    non_compliant: '#dc2626',
  };
  const STATUS_BG = {
    compliant: '#f0fdf4',
    uncertain: '#fffbeb',
    non_compliant: '#fef2f2',
  };
  const STATUS_LABEL = {
    compliant: 'Compliant',
    uncertain: 'Uncertain',
    non_compliant: 'Non-compliant',
  };
  const STATUS_ICON = { compliant: '✔', uncertain: '⚠', non_compliant: '✘' };

  const tableRows = sorted
    .map((r) => {
      const color = STATUS_COLOR[r.status];
      const bg = STATUS_BG[r.status];
      const label = STATUS_LABEL[r.status];
      const icon = STATUS_ICON[r.status];
      const reasonRow = withExplanations
        ? `
      <tr>
        <td colspan="3" style="padding:0 14px 10px 48px;font-size:12px;color:#6b7280;line-height:1.55;background:${bg};">
          ${_esc(r.reason)}
        </td>
      </tr>`
        : '';
      return `
      <tr style="border-top:1px solid #f3f4f6;">
        <td style="padding:10px 14px;vertical-align:top;width:36px;font-size:11px;color:#9ca3af;font-family:monospace;">${
          r.rule_index
        }.</td>
        <td style="padding:10px 6px 10px 0;vertical-align:top;font-size:13px;color:#1f2937;line-height:1.5;">${_esc(
          r.rule
        )}</td>
        <td style="padding:10px 14px;vertical-align:top;white-space:nowrap;text-align:right;">
          <span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;color:${color};background:${bg};border:1px solid ${color}33;padding:3px 9px;border-radius:12px;">
            ${icon} ${label}
          </span>
        </td>
      </tr>
      ${reasonRow}`;
    })
    .join('');

  const html = `<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<title>Compliance Report — CAD2RAG</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=DM+Mono:wght@400&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'DM Sans', -apple-system, sans-serif; color: #111827; background: #fff; padding: 48px 52px; font-size: 14px; }
  @media print { body { padding: 28px 36px; } @page { margin: 16mm 14mm; } }
</style>
</head><body>

<table width="100%" style="margin-bottom:32px;border-bottom:2px solid #e5e7eb;padding-bottom:20px;">
  <tr>
    <td><span style="font-size:22px;font-weight:700;letter-spacing:.02em;">⬡ CAD2RAG</span></td>
    <td style="text-align:right;font-size:12px;color:#6b7280;line-height:1.8;">
      <strong style="color:#374151;display:block;font-size:14px;">Compliance Report</strong>
      ${_esc(filesLabel)}<br>${dateStr}
    </td>
  </tr>
</table>

<table style="width:100%;background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:24px;overflow:hidden;">
  <tr>
    <td style="padding:14px 20px;text-align:center;border-right:1px solid #e5e7eb;">
      <div style="font-size:22px;font-weight:700;color:#16a34a;">${
        summary.compliant
      }</div>
      <div style="font-size:11px;color:#6b7280;margin-top:2px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;">Compliant</div>
    </td>
    <td style="padding:14px 20px;text-align:center;border-right:1px solid #e5e7eb;">
      <div style="font-size:22px;font-weight:700;color:#d97706;">${
        summary.uncertain
      }</div>
      <div style="font-size:11px;color:#6b7280;margin-top:2px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;">Uncertain</div>
    </td>
    <td style="padding:14px 20px;text-align:center;">
      <div style="font-size:22px;font-weight:700;color:#dc2626;">${
        summary.non_compliant
      }</div>
      <div style="font-size:11px;color:#6b7280;margin-top:2px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;">Non-compliant</div>
    </td>
  </tr>
</table>

<p style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:#9ca3af;margin-bottom:12px;">
  Results — sorted by severity
  ${
    withExplanations
      ? ''
      : "<span style='float:right;font-weight:400;text-transform:none;letter-spacing:0;'>Status only view</span>"
  }
</p>

<table width="100%" style="border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
  ${tableRows}
</table>

<p style="margin-top:32px;font-size:11px;color:#d1d5db;">
  Generated by CAD2RAG · ${new Date().toISOString()} · ${total_rules} rules checked
  ${withExplanations ? '' : ' · Explanations omitted'}
</p>

<script>window.onload=function(){window.print();window.onafterprint=function(){window.close();};};<\/script>
</body></html>`;

  const win = window.open('', '_blank');
  win.document.write(html);
  win.document.close();
}

function buildRuleRow(r) {
  const labels = {
    compliant: 'Compliant',
    non_compliant: 'Non-compliant',
    uncertain: 'Uncertain',
  };
  return `
    <div class="cc-rule-row ${r.status}" onclick="toggleRuleReason(this)">
      <div class="cc-rule-left">
        <span class="cc-dot ${r.status}" title="${labels[r.status]}">●</span>
        <span class="cc-rule-num">${r.rule_index}.</span>
        <span class="cc-rule-text">${escHtml(r.rule)}</span>
        <span class="cc-chevron">›</span>
      </div>
      <div class="cc-rule-reason hidden">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;margin-top:2px">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        ${escHtml(r.reason)}
      </div>
    </div>`;
}

function toggleRuleReason(row) {
  const reason = row.querySelector('.cc-rule-reason');
  const chevron = row.querySelector('.cc-chevron');
  const isOpen = !reason.classList.contains('hidden');
  reason.classList.toggle('hidden', isOpen);
  if (chevron) chevron.style.transform = isOpen ? '' : 'rotate(90deg)';
}

// ─── Message helpers ──────────────────────────────────────────────
function appendMessage(role, text, isError = false, filesQueried = []) {
  const messages = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = role === 'user' ? 'You' : 'CAD2RAG';

  const bubble = document.createElement('div');
  bubble.className = `msg-bubble${isError ? ' error' : ''}`;
  bubble.textContent = text;

  div.appendChild(label);
  div.appendChild(bubble);

  if (filesQueried && filesQueried.length > 1) {
    const tag = document.createElement('div');
    tag.className = 'msg-sources';
    tag.textContent = `Sources: ${filesQueried.join(' · ')}`;
    div.appendChild(tag);
  }

  messages.appendChild(div);
  document.getElementById('chatArea').scrollTop = 99999;
}

function addTyping() {
  const messages = document.getElementById('messages');
  const id = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = id;
  const lbl = document.createElement('div');
  lbl.className = 'msg-label';
  lbl.textContent = 'CAD2RAG';
  const typ = document.createElement('div');
  typ.className = 'typing';
  typ.innerHTML = '<span></span><span></span><span></span>';
  div.appendChild(lbl);
  div.appendChild(typ);
  messages.appendChild(div);
  document.getElementById('chatArea').scrollTop = 99999;
  return id;
}
function removeTyping(id) {
  document.getElementById(id)?.remove();
}

// ─── Utility ──────────────────────────────────────────────────────
function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendQuery();
  }
}
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

function showBannerError(msg) {
  const b = document.getElementById('errorBanner');
  b.textContent = msg;
  b.style.display = 'block';
  clearTimeout(b._t);
  b._t = setTimeout(() => {
    b.style.display = 'none';
  }, 4000);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function resetApp() {
  state = {
    sessionId: null,
    fileType: state.fileType,
    queue: [],
    loading: false,
    hasPDF: false,
    rules: [],
    lastReportId: null,
  };
  closeComplianceDrawer();
  ['sessionPanel'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  ['chatArea', 'inputBar', 'toolbar'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  const ctb = document.getElementById('complianceTriggerBtn');
  if (ctb) ctb.style.display = 'none';
  document.getElementById('emptyState').style.display = 'flex';
  document.getElementById('processAllBtn').style.display = 'none';
  document.getElementById('fileQueue').innerHTML = '';
  document.getElementById('messages').innerHTML = '';
  document.getElementById('fileInput').value = '';
  document.getElementById('errorBanner').style.display = 'none';
  document.getElementById(
    'slotsLeft'
  ).textContent = `${MAX_FILES} slots remaining`;
  renderRuleList();
}

// Init
renderRuleList();

// ─── Export rules ─────────────────────────────────────────────────
function exportRules(format) {
  if (state.rules.length === 0) {
    showBannerError('No rules to export.');
    return;
  }

  if (format === 'txt') {
    const content = state.rules.map((r, i) => `${i + 1}. ${r}`).join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `compliance-rules-${_dateStamp()}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
    return;
  }

  if (format === 'pdf') {
    const rows = state.rules
      .map(
        (r, i) => `
      <tr>
        <td class="num">${i + 1}</td>
        <td class="rule">${_esc(r)}</td>
      </tr>`
      )
      .join('');

    const win = window.open('', '_blank');
    win.document.write(`<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<title>Compliance Rules — CAD2RAG</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=DM+Mono:wght@400&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'DM Sans', sans-serif; color: #1a202c; background: #fff; padding: 48px 56px; }
  header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 36px; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; }
  .logo { font-size: 22px; font-weight: 700; color: #1a202c; letter-spacing: .02em; }
  .logo span { color: #4f8ef7; }
  .meta { text-align: right; font-size: 12px; color: #718096; line-height: 1.6; }
  h1 { font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: #718096; margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; }
  tr { border-bottom: 1px solid #edf2f7; }
  tr:last-child { border-bottom: none; }
  td { padding: 10px 8px; vertical-align: top; font-size: 13px; line-height: 1.55; }
  td.num { width: 36px; color: #a0aec0; font-family: 'DM Mono', monospace; font-size: 11px; padding-top: 12px; }
  td.rule { color: #2d3748; }
  tr:nth-child(even) td { background: #f7fafc; }
  footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #a0aec0; }
  @media print {
    body { padding: 32px 40px; }
    @page { margin: 20mm 18mm; }
  }
</style>
</head><body>
<header>
  <div class="logo">⬡ CAD<span>2</span>RAG</div>
  <div class="meta">
    Compliance Rules<br>
    ${state.rules.length} rule${state.rules.length !== 1 ? 's' : ''}<br>
    ${new Date().toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })}
  </div>
</header>
<h1>Compliance Rules</h1>
<table>${rows}</table>
<footer>Generated by CAD2RAG · ${new Date().toISOString()}</footer>
<script>
  window.onload = function() {
    window.print();
    window.onafterprint = function() { window.close(); };
  };
<\/script>
</body></html>`);
    win.document.close();
  }
}

function _dateStamp() {
  return new Date().toISOString().slice(0, 10);
}
function _esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
