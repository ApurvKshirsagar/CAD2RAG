const API = 'http://127.0.0.1:8000/api';

let state = {
  sessionId: null,
  fileType: 'dxf',
  file: null,
  loading: false,
};

// ── File type toggle ────────────────────────────────────────────────
function setFileType(type) {
  state.fileType = type;
  state.file = null;

  document.getElementById('btn-dxf').classList.toggle('active', type === 'dxf');
  document.getElementById('btn-pdf').classList.toggle('active', type === 'pdf');
  document.getElementById('fileTypeLabel').textContent = type.toUpperCase();
  document.getElementById('fileInput').accept =
    type === 'dxf' ? '.dxf' : '.pdf';
  document.getElementById('fileInfo').style.display = 'none';
}

// ── Drag & drop ─────────────────────────────────────────────────────
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
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
}
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) setFile(file);
}

function setFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (ext !== state.fileType) {
    alert(`Please upload a .${state.fileType} file, or switch the toggle.`);
    return;
  }
  state.file = file;
  document.getElementById('fileName').textContent = file.name;
  document.getElementById('fileInfo').style.display = 'block';
}

// ── Upload ──────────────────────────────────────────────────────────
async function uploadFile() {
  if (!state.file || state.loading) return;

  state.loading = true;
  const btn = document.getElementById('uploadBtn');
  const btnText = document.getElementById('uploadBtnText');

  btn.disabled = true;
  btnText.textContent = 'Processing...';

  // Show progress bar
  const fileInfo = document.getElementById('fileInfo');
  const bar = document.createElement('div');
  bar.className = 'progress-bar';
  bar.innerHTML = '<div class="progress-fill"></div>';
  fileInfo.appendChild(bar);

  const formData = new FormData();
  formData.append('file', state.file);

  try {
    const res = await fetch(`${API}/upload`, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || 'Upload failed');

    state.sessionId = data.session_id;

    // Show session info in sidebar
    showSessionPanel(data);

    // Switch to chat view
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('chatArea').style.display = 'flex';
    document.getElementById('inputBar').style.display = 'block';

    // Welcome message
    appendMessage('assistant', buildWelcomeMessage(data));
  } catch (err) {
    appendMessage('assistant', `Upload failed: ${err.message}`, true);
    document.getElementById('emptyState').style.display = 'flex';
  } finally {
    bar.remove();
    btn.disabled = false;
    btnText.textContent = 'Process File';
    state.loading = false;
  }
}

function buildWelcomeMessage(data) {
  if (data.file_type === 'dxf') {
    const s = data.summary;
    return (
      `DXF file loaded successfully.\n\n` +
      `📐 Filename: ${data.filename}\n` +
      `🗂 Layers: ${s.layers}\n` +
      `🔷 Entities: ${s.entities}\n` +
      `📏 Units: ${s.metadata?.units || 'N/A'}\n\n` +
      `You can now ask questions like:\n` +
      `• "What entity types are in this drawing?"\n` +
      `• "How many lines are there?"\n` +
      `• "Describe the layers in this file"`
    );
  } else {
    const s = data.summary;
    return (
      `PDF loaded successfully.\n\n` +
      `📄 Filename: ${data.filename}\n` +
      `📖 Pages: ${s.total_pages}\n` +
      `📝 Pages with text: ${s.pages_with_text}\n\n` +
      `You can now ask questions about the document content.`
    );
  }
}

function showSessionPanel(data) {
  const panel = document.getElementById('sessionPanel');
  const info = document.getElementById('sessionInfo');
  panel.style.display = 'block';
  document.getElementById('upload-section')?.style;

  let html = `<strong>Type:</strong> ${data.file_type.toUpperCase()}<br>`;
  html += `<strong>File:</strong> ${data.filename}<br>`;
  html += `<strong>Status:</strong> ✅ Ready<br>`;
  if (data.file_type === 'dxf') {
    html += `<strong>Entities:</strong> ${data.summary.entities}<br>`;
    html += `<strong>Layers:</strong> ${data.summary.layers}`;
  } else {
    html += `<strong>Pages:</strong> ${data.summary.total_pages}`;
  }
  info.innerHTML = html;
}

// ── Query ───────────────────────────────────────────────────────────
async function sendQuery() {
  const input = document.getElementById('questionInput');
  const question = input.value.trim();

  if (!question || state.loading || !state.sessionId) return;

  state.loading = true;
  input.value = '';
  autoResize(input);

  document.getElementById('sendBtn').disabled = true;

  // Add user message
  appendMessage('user', question);

  // Add typing indicator
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

// ── Message helpers ─────────────────────────────────────────────────
function appendMessage(role, text, isError = false) {
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
  messages.appendChild(div);

  // Scroll to bottom
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

// ── UI helpers ──────────────────────────────────────────────────────
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
    sessionId: null,
    fileType: state.fileType,
    file: null,
    loading: false,
  };

  document.getElementById('sessionPanel').style.display = 'none';
  document.getElementById('fileInfo').style.display = 'none';
  document.getElementById('chatArea').style.display = 'none';
  document.getElementById('inputBar').style.display = 'none';
  document.getElementById('emptyState').style.display = 'flex';
  document.getElementById('messages').innerHTML = '';
  document.getElementById('fileName').textContent = '';
  document.getElementById('fileInput').value = '';
}
