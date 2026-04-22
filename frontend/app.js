const API = 'http://127.0.0.1:8000/api';

// ── App state ────────────────────────────────────────────────────────
let state = {
  batchSessionId: null, // current batch session on the backend
  files: [], // [{name, type, status:'queued'|'processing'|'done'|'error', summary}]
  sessionReady: false, // true once ≥1 file processed successfully
  loading: false,
  activeFileType: 'pdf', // default toggle selection
};

const MAX_FILES = 10;

// ── Boot ─────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  setFileType('pdf');
});

// ── File type toggle ─────────────────────────────────────────────────
function setFileType(type) {
  state.activeFileType = type;
  document.getElementById('btn-dxf').classList.toggle('active', type === 'dxf');
  document.getElementById('btn-pdf').classList.toggle('active', type === 'pdf');
  document.getElementById('fileTypeLabel').textContent = type.toUpperCase();
  document.getElementById('fileInput').accept =
    type === 'dxf' ? '.dxf' : '.pdf';
}

// ── Drag & drop ──────────────────────────────────────────────────────
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
  const files = Array.from(e.dataTransfer.files);
  files.forEach((f) => queueFile(f));
}
function handleFileSelect(e) {
  const files = Array.from(e.target.files);
  files.forEach((f) => queueFile(f));
  e.target.value = ''; // reset so same file can be re-selected
}

// ── Queue a file locally (no upload yet) ─────────────────────────────
function queueFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (ext !== 'dxf' && ext !== 'pdf') {
    showToast(
      `Skipped "${file.name}": only DXF and PDF files are supported.`,
      'error'
    );
    return;
  }
  if (state.files.length >= MAX_FILES) {
    showToast(`Maximum ${MAX_FILES} files per session reached.`, 'error');
    return;
  }
  // Check duplicate name
  if (state.files.some((f) => f.name === file.name)) {
    showToast(`"${file.name}" is already in the list.`, 'warn');
    return;
  }
  state.files.push({
    name: file.name,
    type: ext,
    status: 'queued',
    file,
    summary: null,
  });
  renderFileList();
  updateProcessBtn();
}

// ── Render the file queue in the sidebar ─────────────────────────────
function renderFileList() {
  const list = document.getElementById('fileQueue');
  list.innerHTML = '';

  if (state.files.length === 0) {
    list.innerHTML = '<div class="queue-empty">No files added yet</div>';
    return;
  }

  state.files.forEach((f, idx) => {
    const item = document.createElement('div');
    item.className = 'queue-item';
    item.id = `qi-${idx}`;

    const icon = f.type === 'dxf' ? '⬡' : '📄';
    const statusIcon = {
      queued: '<span class="status-dot queued" title="Queued"></span>',
      processing:
        '<span class="status-dot processing" title="Processing…">⟳</span>',
      done: '<span class="status-dot done" title="Ready">✓</span>',
      error: '<span class="status-dot error" title="Failed">✗</span>',
    }[f.status];

    // Only show remove button for queued files (not mid-processing)
    const removeBtn =
      f.status === 'queued'
        ? `<button class="remove-btn" onclick="removeFile(${idx})" title="Remove">×</button>`
        : '';

    item.innerHTML = `
      <span class="qi-icon">${icon}</span>
      <span class="qi-name" title="${f.name}">${f.name}</span>
      ${statusIcon}
      ${removeBtn}
    `;
    list.appendChild(item);
  });
}

function removeFile(idx) {
  state.files.splice(idx, 1);
  renderFileList();
  updateProcessBtn();
}

function updateProcessBtn() {
  const btn = document.getElementById('processBtn');
  const queued = state.files.filter((f) => f.status === 'queued').length;
  btn.disabled = queued === 0 || state.loading;
  btn.textContent =
    queued > 0
      ? `Process ${queued} file${queued > 1 ? 's' : ''}`
      : 'Process Files';
}

// ── Process all queued files ──────────────────────────────────────────
async function processFiles() {
  const queued = state.files.filter((f) => f.status === 'queued');
  if (queued.length === 0 || state.loading) return;

  state.loading = true;
  updateProcessBtn();

  try {
    // Create batch session if we don't have one yet
    if (!state.batchSessionId) {
      const res = await fetch(`${API}/batch/create`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok)
        throw new Error(data.detail || 'Failed to create batch session');
      state.batchSessionId = data.batch_session_id;
    }

    // Upload queued files one by one
    let anySuccess = false;
    for (const f of queued) {
      f.status = 'processing';
      renderFileList();

      try {
        const formData = new FormData();
        formData.append('file', f.file);

        const res = await fetch(`${API}/batch/${state.batchSessionId}/add`, {
          method: 'POST',
          body: formData,
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || 'Upload failed');

        f.status = 'done';
        f.summary = data.added.summary;
        anySuccess = true;
      } catch (err) {
        f.status = 'error';
        f.errorMsg = err.message;
      }

      renderFileList();
    }

    if (anySuccess) {
      state.sessionReady = true;
      showChatArea();
      updateSessionPanel();
    }
  } catch (err) {
    showToast(`Session error: ${err.message}`, 'error');
  } finally {
    state.loading = false;
    updateProcessBtn();
  }
}

// ── Show chat ─────────────────────────────────────────────────────────
function showChatArea() {
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('chatArea').style.display = 'flex';
  document.getElementById('inputBar').style.display = 'block';

  const done = state.files.filter((f) => f.status === 'done');
  const names = done.map((f) => `• ${f.name}`).join('\n');
  appendMessage(
    'assistant',
    `✅ ${done.length} file${
      done.length > 1 ? 's' : ''
    } ready for questions:\n${names}\n\n` +
      `You can now ask questions across all files, e.g.:\n` +
      `• "Which room is beside the operation room?"\n` +
      `• "Compare the layouts of both floor plans"\n` +
      `• "What is the total area mentioned across all documents?"`
  );
}

// ── Session panel (sidebar info) ──────────────────────────────────────
function updateSessionPanel() {
  const panel = document.getElementById('sessionPanel');
  const info = document.getElementById('sessionInfo');
  panel.style.display = 'block';

  const done = state.files.filter((f) => f.status === 'done');
  const error = state.files.filter((f) => f.status === 'error');

  let html = `<strong>Files ready:</strong> ${done.length}<br>`;
  if (error.length)
    html += `<strong style="color:var(--danger)">Failed:</strong> ${error.length}<br>`;
  html += `<hr style="border-color:var(--border);margin:8px 0">`;

  done.forEach((f) => {
    html += `<div class="si-file">`;
    html += `<span class="si-icon">${f.type === 'dxf' ? '⬡' : '📄'}</span>`;
    html += `<span class="si-name">${f.name}</span>`;
    html += `</div>`;
  });

  info.innerHTML = html;
}

// ── Query ─────────────────────────────────────────────────────────────
async function sendQuery() {
  const input = document.getElementById('questionInput');
  const question = input.value.trim();
  if (!question || state.loading || !state.batchSessionId) return;

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
      body: JSON.stringify({ session_id: state.batchSessionId, question }),
    });
    const data = await res.json();
    removeTyping(typingId);
    if (!res.ok) throw new Error(data.detail || 'Query failed');
    appendMessage('assistant', data.answer);
  } catch (err) {
    removeTyping(typingId);
    appendMessage('assistant', `Error: ${err.message}`, true);
  } finally {
    state.loading = false;
    document.getElementById('sendBtn').disabled = false;
    input.focus();
  }
}

// ── Message helpers ───────────────────────────────────────────────────
function appendMessage(role, text, isError = false) {
  const messages = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = role === 'user' ? 'You' : 'CAD2RAG';

  const bubble = document.createElement('div');
  bubble.className = `msg-bubble${isError ? ' error' : ''}`;
  // Preserve newlines
  bubble.style.whiteSpace = 'pre-wrap';
  bubble.textContent = text;

  div.appendChild(label);
  div.appendChild(bubble);
  messages.appendChild(div);
  document.getElementById('chatArea').scrollTop = 99999;
}

function addTyping() {
  const messages = document.getElementById('messages');
  const id = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = id;

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = 'CAD2RAG';

  const typing = document.createElement('div');
  typing.className = 'typing';
  typing.innerHTML = '<span></span><span></span><span></span>';

  div.appendChild(label);
  div.appendChild(typing);
  messages.appendChild(div);
  document.getElementById('chatArea').scrollTop = 99999;
  return id;
}

function removeTyping(id) {
  document.getElementById(id)?.remove();
}

// ── Toast notification ────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add('show'), 10);
  setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => t.remove(), 300);
  }, 3500);
}

// ── UI helpers ────────────────────────────────────────────────────────
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

function resetApp() {
  state = {
    batchSessionId: null,
    files: [],
    sessionReady: false,
    loading: false,
    activeFileType: state.activeFileType,
  };

  document.getElementById('sessionPanel').style.display = 'none';
  document.getElementById('chatArea').style.display = 'none';
  document.getElementById('inputBar').style.display = 'none';
  document.getElementById('emptyState').style.display = 'flex';
  document.getElementById('messages').innerHTML = '';
  document.getElementById('fileInput').value = '';
  renderFileList();
  updateProcessBtn();
}
