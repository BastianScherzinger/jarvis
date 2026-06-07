/* ═══════════════════════ CONFIG ═════════════════════════════════ */
const AGENT_META = {
  library:       { name: "LibraryScout",  icon: "📚", color: "#a78bfa" },
  research:      { name: "ResearchBot",   icon: "🔬", color: "#38bdf8" },
  senior_dev:    { name: "SeniorPy",      icon: "⚙️", color: "#34d399" },
  ux:            { name: "UXCrafter",     icon: "🎨", color: "#fbbf24" },
  code_reviewer: { name: "ReviewMaster",  icon: "👁️", color: "#60a5fa" },
  debugger:      { name: "DebugHunter",   icon: "🐛", color: "#f87171" },
  bug_fixer:     { name: "BugSlayer",     icon: "🔧", color: "#fb923c" },
  bug_expert:    { name: "BugWizard",     icon: "🧙", color: "#c084fc" },
  performance:   { name: "SpeedDemon",    icon: "⚡", color: "#22d3ee" },
  security:      { name: "SecureGuard",   icon: "🔒", color: "#f43f5e" },
};

const TOOL_META = {
  read_file:        { icon: "📄", label: "Datei lesen" },
  write_file:       { icon: "💾", label: "Datei schreiben" },
  run_command:      { icon: "💻", label: "Command ausführen" },
  list_directory:   { icon: "📁", label: "Verzeichnis auflisten" },
  search_files:     { icon: "🔍", label: "Dateien suchen" },
  delegate_to_agent:{ icon: "🤖", label: "Agent delegieren" },
};

/* ═══════════════════════ STATE ══════════════════════════════════ */
const state = {
  streaming:      false,
  currentMsgEl:   null,   // the current assistant bubble element
  currentBubble:  null,
  currentText:    "",
  toolCards:      {},     // tool_id → card element
  agentKeys:      {},     // tool_id → agent_key
};

/* ═══════════════════════ GLOBAL ERROR CATCHING ══════════════════ */
window.onerror = function(msg, src, line, col, err) {
  console.error("[JS-FEHLER]", msg, "→", src + ":" + line + ":" + col, err);
};
window.addEventListener("unhandledrejection", e => {
  console.error("[PROMISE-FEHLER]", e.reason);
});

/* ═══════════════════════ INIT ═══════════════════════════════════ */
document.addEventListener("DOMContentLoaded", () => {
  console.log("[JARVIS] DOMContentLoaded — init start");
  // marked v5+ API: use() statt setOptions()
  try {
    if (typeof marked.use === "function") {
      marked.use({ breaks: true, gfm: true });
    } else if (typeof marked.setOptions === "function") {
      marked.setOptions({ breaks: true, gfm: true });
    }
    console.log("[JARVIS] marked OK");
  } catch (e) {
    console.warn("[JARVIS] marked config fehlgeschlagen:", e);
  }
  vrInit();
  console.log("[JARVIS] init komplett");
});

/* ═══════════════════════ SEND MESSAGE ═══════════════════════════ */
let _streamAbort = null;

async function sendMessage() {
  if (state.streaming) return;
  const input = document.getElementById("msg-input");
  const text  = input.value.trim();
  if (!text) return;

  input.value = "";
  autoResize(input);
  showChat();
  addMessage("user", text);

  state.streaming = true;
  setStatus("active", "JARVIS denkt…");
  setLiveDot(true);
  disableSend(true);
  clearActivityFeed();
  if (vrActive) setVoiceLabel("Warte...");
  if (typeof window.brainGrow === 'function') window.brainGrow();

  const msgEl  = addMessage("assistant", "");
  state.currentMsgEl  = msgEl;
  state.currentBubble = msgEl.querySelector(".msg-bubble");
  state.currentText   = "";

  _streamAbort = new AbortController();
  try {
    const resp = await fetch("/api/chat", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ message: text }),
      signal:  _streamAbort.signal,
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try { handleEvent(JSON.parse(line.slice(6))); } catch { /* skip */ }
        }
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      if (state.currentBubble)
        state.currentBubble.innerHTML = `<span style="color:var(--danger)">Fehler: ${err.message}</span>`;
    }
  } finally {
    _streamAbort      = null;
    state.streaming   = false;
    disableSend(false);
    setStatus("idle", "Bereit");
    setLiveDot(false);
    // Mic nur freigeben wenn kein TTS mehr aussteht
    if (vrActive && !_ttsPending && !_ttsSource && !_ttsAudio) {
      vrBusy = false;
      setVoiceLabel("Hoere zu...");
      vrVadTick();
    }
    document.getElementById("msg-input").focus();
  }
}

function abortStream() {
  if (_streamAbort) { _streamAbort.abort(); _streamAbort = null; }
  state.streaming = false;
  disableSend(false);
  setStatus("idle", "Bereit");
  setLiveDot(false);
  if (vrActive) setVoiceLabel("Hoere zu...");
}

/* ═══════════════════════ EVENT HANDLER ══════════════════════════ */
function handleEvent(data) {
  switch (data.type) {
    case "status":
      setStatus("active", data.text);
      break;

    case "thinking":
      addThinkingCard(data.text);
      break;

    case "tool_call":
      if (data.tool === "delegate_to_agent") {
        addAgentCard(data);
      } else {
        addToolCard(data);
      }
      break;

    case "tool_result":
      finishToolCard(data);
      break;

    case "tool_error":
      errorToolCard(data);
      break;

    case "token":
      appendToken(data.text);
      break;

    case "spoken":
      _ttsPending = true;
      playSpoken(data.text, data.id || "");
      break;

    case "done":
      finalizeMessage();
      refreshWorkspace();
      if (data.usage) updateTokenDisplay(data.usage);
      break;
  }
}

/* ═══════════════════════ TOKEN STREAMING ════════════════════════ */
function appendToken(text) {
  if (!state.currentBubble) return;
  state.currentText += text;
  state.currentBubble.innerHTML = renderMd(state.currentText);
  hljs.highlightAll();
  scrollMessages();
}

function finalizeMessage() {
  if (!state.currentBubble) return;
  state.currentBubble.innerHTML = renderMd(state.currentText);
  hljs.highlightAll();
  scrollMessages();
  state.currentMsgEl  = null;
  state.currentBubble = null;
  state.currentText   = "";
  state.toolCards     = {};
}

/* ═══════════════════════ ACTIVITY CARDS ════════════════════════ */
function clearActivityFeed() {
  document.getElementById("ap-empty").style.display  = "flex";
  document.getElementById("activity-feed").innerHTML = "";
  state.toolCards = {};
  state.agentKeys = {};
}

function addThinkingCard(text) {
  const feed = document.getElementById("activity-feed");
  document.getElementById("ap-empty").style.display = "none";
  const card = document.createElement("div");
  card.className = "thinking-card";
  card.textContent = text.slice(0, 200) + (text.length > 200 ? "…" : "");
  feed.appendChild(card);
  feed.scrollTop = feed.scrollHeight;
}

function addToolCard(data) {
  const feed = document.getElementById("activity-feed");
  document.getElementById("ap-empty").style.display = "none";

  const meta    = TOOL_META[data.tool] || { icon: "🔧", label: data.tool };
  const preview = formatInput(data.tool, data.input);

  const card = document.createElement("div");
  card.className = "activity-card";
  card.id = `card-${data.tool_id}`;
  card.innerHTML = `
    <div class="ac-head">
      <div class="ac-icon">${meta.icon}</div>
      <span class="ac-label">${meta.label}</span>
      <div class="ac-status"><div class="spinner"></div></div>
    </div>
    ${preview ? `<div class="ac-preview">${escHtml(preview)}</div>` : ""}
  `;
  feed.appendChild(card);
  feed.scrollTop = feed.scrollHeight;
  state.toolCards[data.tool_id] = card;
}

function addAgentCard(data) {
  const feed = document.getElementById("activity-feed");
  document.getElementById("ap-empty").style.display = "none";

  const agent = AGENT_META[data.agent_key] || { name: data.agent_key, icon: "🤖", color: "#888" };
  const task  = (data.input?.task || "").slice(0, 120);

  const card = document.createElement("div");
  card.className = `activity-card agent-card ac-${data.agent_key}`;
  card.id = `card-${data.tool_id}`;
  card.innerHTML = `
    <div class="ac-head">
      <div class="ac-agent-av" style="background:${agent.color}">${agent.name[0]}</div>
      <span class="ac-label">${agent.name}</span>
      <div class="ac-status"><div class="spinner"></div></div>
    </div>
    ${task ? `<div class="ac-preview">${escHtml(task)}…</div>` : ""}
  `;
  feed.appendChild(card);
  feed.scrollTop = feed.scrollHeight;
  state.toolCards[data.tool_id] = card;
  state.agentKeys[data.tool_id] = data.agent_key;
  if (typeof window.activateAgentOrb === 'function') window.activateAgentOrb(data.agent_key);
}

function finishToolCard(data) {
  const card = state.toolCards[data.tool_id];
  if (!card) return;

  const statusEl = card.querySelector(".ac-status");
  if (statusEl) statusEl.innerHTML = `<span style="color:var(--accent)">✓</span>`;

  const preview = (data.result || "").trim().split("\n")[0].slice(0, 100);
  if (preview) {
    let pre = card.querySelector(".ac-preview");
    if (!pre) {
      pre = document.createElement("div");
      pre.className = "ac-preview";
      card.appendChild(pre);
    }
    // append result below existing preview
    pre.innerHTML += `<div style="margin-top:4px;color:var(--accent);opacity:.7">${escHtml(preview)}</div>`;
  }

  card.querySelector(".ac-head")?.style && (card.style.borderColor = "rgba(0,229,160,.2)");
  const agentKey = state.agentKeys[data.tool_id];
  if (agentKey && typeof window.deactivateAgentOrb === 'function') window.deactivateAgentOrb(agentKey);
  const feed = document.getElementById("activity-feed");
  feed.scrollTop = feed.scrollHeight;
}

function errorToolCard(data) {
  const card = state.toolCards[data.tool_id];
  if (!card) return;
  const statusEl = card.querySelector(".ac-status");
  if (statusEl) statusEl.innerHTML = `<span style="color:var(--danger)">✕</span>`;
  card.style.borderColor = "rgba(244,63,94,.25)";
}

function addActivityCard(type, { label, preview }) {
  const feed = document.getElementById("activity-feed");
  document.getElementById("ap-empty").style.display = "none";
  const card = document.createElement("div");
  card.className = "activity-card";
  card.innerHTML = `
    <div class="ac-head">
      <div class="ac-icon">⚠️</div>
      <span class="ac-label">${label}</span>
    </div>
    ${preview ? `<div class="ac-preview">${escHtml(preview)}</div>` : ""}
  `;
  feed.appendChild(card);
}

/* ═══════════════════════ MESSAGES ═══════════════════════════════ */
function showChat() {
  document.getElementById("welcome").style.display  = "none";
  const msgArea = document.getElementById("messages");
  msgArea.style.display = "flex";
}

function addMessage(role, content) {
  const msgArea = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = `message ${role}`;

  if (role === "assistant") {
    div.innerHTML = `
      <div class="msg-av jarvis">
        <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
          <polygon points="10,2 18,6.5 18,13.5 10,18 2,13.5 2,6.5" stroke="currentColor" stroke-width="1.5" fill="none"/>
          <circle cx="10" cy="10" r="2.5" fill="currentColor" opacity=".6"/>
        </svg>
      </div>
      <div class="msg-body">
        <span class="msg-name">JARVIS</span>
        <div class="msg-bubble">${content ? renderMd(content) : '<span class="blink">▍</span>'}</div>
        <span class="msg-time">${ts()}</span>
      </div>`;
  } else {
    div.innerHTML = `
      <div class="msg-av user-av">Du</div>
      <div class="msg-body">
        <span class="msg-name" style="color:var(--text-3)">Du</span>
        <div class="msg-bubble">${escHtml(content).replace(/\n/g, "<br>")}</div>
        <span class="msg-time">${ts()}</span>
      </div>`;
  }

  msgArea.appendChild(div);
  scrollMessages();
  return div;
}

function scrollMessages() {
  const m = document.getElementById("messages");
  m.scrollTop = m.scrollHeight;
}

/* ═══════════════════════ WORKSPACE ══════════════════════════════ */
async function refreshWorkspace() {
  try {
    const data = await fetch("/api/workspace").then(r => r.json());
    renderWorkspaceList("ws-tasks",   data.tasks,   "tasks");
    renderWorkspaceList("ws-results", data.results, "results");
  } catch { /* ignore */ }
}

function renderWorkspaceList(elId, files, folder) {
  const el = document.getElementById(elId);
  if (!files || !files.length) {
    el.innerHTML = `<span class="ws-empty">Noch keine Dateien</span>`;
    return;
  }
  el.innerHTML = files.map(f => `
    <div class="ws-file" onclick="openFile('${folder}','${f.name}')">
      <span class="ws-file-icon">${folder === "tasks" ? "📋" : "✅"}</span>
      <span class="ws-file-name">${f.name}</span>
      <span class="ws-file-size">${formatSize(f.size)}</span>
    </div>`).join("");
}

async function openFile(folder, name) {
  try {
    const text  = await fetch(`/api/workspace/${folder}/${name}`).then(r => r.text());
    document.getElementById("modal-title").textContent = name;
    document.getElementById("modal-body").textContent  = text;
    document.getElementById("modal").classList.add("open");
  } catch (e) {
    showToast("Datei konnte nicht geladen werden");
  }
}

function closeModal() {
  document.getElementById("modal").classList.remove("open");
}

/* ═══════════════════════ TAB SWITCHING ══════════════════════════ */
function switchTab(tab) {
  document.getElementById("ap-activity").style.display  = tab === "activity"  ? "flex" : "none";
  document.getElementById("ap-workspace").style.display = tab === "workspace" ? "flex" : "none";
  document.getElementById("tab-activity").classList.toggle("active",  tab === "activity");
  document.getElementById("tab-workspace").classList.toggle("active", tab === "workspace");
  if (tab === "workspace") refreshWorkspace();
}

/* ═══════════════════════ RESET ══════════════════════════════════ */
async function resetAll() {
  await fetch("/api/reset", { method: "POST" });
  document.getElementById("messages").innerHTML  = "";
  document.getElementById("messages").style.display = "none";
  document.getElementById("welcome").style.display  = "";
  clearActivityFeed();
  showToast("Konversation zurückgesetzt");
}

/* ═══════════════════════ STATUS BAR ════════════════════════════ */
function setStatus(mode, label) {
  document.querySelector(".status-dot").className  = `status-dot ${mode}`;
  document.getElementById("status-label").textContent = label;
}
function setLiveDot(on) {
  document.getElementById("live-dot").className = `live-dot${on ? " active" : ""}`;
}
function disableSend(v) {
  document.getElementById("send-btn").disabled = v;
}

/* ═══════════════════════ UTILS ══════════════════════════════════ */
function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

// Global shortcut: Ctrl+M = toggle mic
document.addEventListener("keydown", e => {
  if (e.ctrlKey && e.key === "m") { e.preventDefault(); toggleVoice(); }
});

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 150) + "px";
}

function insertPrompt(text) {
  const inp = document.getElementById("msg-input");
  inp.value = text;
  autoResize(inp);
  inp.focus();
}

function renderMd(text) {
  try { return marked.parse(text); }
  catch { return escHtml(text); }
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function ts() {
  return new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  return (bytes / 1024).toFixed(1) + " KB";
}

function formatInput(tool, input) {
  if (!input) return "";
  if (tool === "read_file")      return input.path || "";
  if (tool === "write_file")     return input.path || "";
  if (tool === "run_command")    return (input.command || "").slice(0, 80);
  if (tool === "list_directory") return input.path || "";
  if (tool === "search_files")   return `${input.pattern} in ${input.path}`;
  return "";
}

/* ═══════════════════════ VOICE (Continuous VAD) ═════════════════
 * Dauerhoeren: Mikrofon immer an, automatische Spracherkennung.
 * Ablauf: Mikrofon-Button → VAD-Loop → Sprache erkannt → Aufnahme
 *         → Stille 1.2s → Flask → Google Speech → Auto-Send.
 * ════════════════════════════════════════════════════════════════ */

const VAD_THRESHOLD    = 0.02;   // RMS-Schwelle (Float32 -1..1)
const VAD_SILENCE_MS   = 750;    // Stille nach Sprache -> senden (schneller)
const VAD_MIN_SPEAK_MS = 300;    // Mindest-Sprechdauer (Rauschen ignorieren)

let vrActive      = false;
let vrLang        = 'de-DE';
let vrDeviceId    = null;
let vrStream      = null;
let vrAudioCtx    = null;
let vrAnalyser    = null;
let vrRecorder    = null;
let vrBlobs       = [];
let vrMimeType    = 'audio/webm';
let vrVadState    = 'idle';    // idle | waiting | speaking | silence
let vrSpeechStart = 0;
let vrSilenceStart = 0;
let vrAnimFrame   = null;
let vrBusy        = false;     // Transkription laeuft

const PREFER_MIC = ['realtek', 'mikrofon', 'microphone', 'headset', 'built-in', 'array'];
const SKIP_MIC   = ['soundmapper', 'stereomix', 'stereo mix', 'virtual', 'loopback', 'output'];

async function vrFindMic() {
  try {
    const tmp = await navigator.mediaDevices.getUserMedia({ audio: true });
    tmp.getTracks().forEach(t => t.stop());
  } catch { return; }

  const devices = await navigator.mediaDevices.enumerateDevices();
  const mics    = devices.filter(d => d.kind === 'audioinput');
  let best = null, bestScore = -1;
  for (const d of mics) {
    const name = d.label.toLowerCase();
    if (SKIP_MIC.some(s => name.includes(s))) continue;
    let score = 0;
    if (PREFER_MIC.some(p => name.includes(p))) score += 10;
    if (d.deviceId === 'default') score -= 5;
    if (score > bestScore) { bestScore = score; best = d; }
  }
  if (best) {
    vrDeviceId = best.deviceId;
    console.log('[VOICE] Mic:', best.label, '->', vrDeviceId);
    setVoiceLabel(best.label.slice(0, 28));
  }
}

/* ── Init ─────────────────────────────────────────────────────── */
function vrInit() {
  console.log('[VOICE] vrInit');
  setVoiceDot('connected');
  setVoiceLabel('Mic suche...');
  vrFindMic()
    .then(() => { setVoiceDot('connected'); setVoiceLabel('Klick zum Starten'); })
    .catch(() => setVoiceLabel('Bereit'));

  // Auto-Start beim ersten Klick / Tastendruck auf der Seite
  function _autoStart() {
    if (!vrActive) vrStart().catch(e => console.warn('[VOICE] auto-start:', e));
  }
  document.addEventListener('click',   _autoStart, { once: true });
  document.addEventListener('keydown', _autoStart, { once: true });
}

/* ── Toggle ───────────────────────────────────────────────────── */
function toggleVoice() {
  vrActive ? vrStop() : vrStart();
}

/* ── Start continuous listening ───────────────────────────────── */
async function vrStart() {
  if (vrActive) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert('Kein Mikrofon-Zugriff. Bitte Chrome oder Edge verwenden.');
    return;
  }

  try {
    const constraint = vrDeviceId
      ? { deviceId: { exact: vrDeviceId }, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      : { channelCount: 1, echoCancellation: true, noiseSuppression: true };
    vrStream = await navigator.mediaDevices.getUserMedia({ audio: constraint, video: false });
    console.log('[VOICE] Stream OK:', vrStream.getAudioTracks().map(t => t.label));
  } catch (err) {
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      alert('Mikrofon-Berechtigung verweigert!\nKlicke auf das Schloss-Symbol -> Erlauben -> Seite neu laden');
    } else {
      alert('Mikrofon-Fehler: ' + err.name + ' - ' + err.message);
    }
    return;
  }

  vrAudioCtx  = new AudioContext();
  await vrAudioCtx.resume();   // AudioContext aus Suspension holen
  vrAnalyser  = vrAudioCtx.createAnalyser();
  vrAnalyser.fftSize = 1024;
  vrAnalyser.smoothingTimeConstant = 0.4;
  vrAudioCtx.createMediaStreamSource(vrStream).connect(vrAnalyser);

  vrActive    = true;
  vrVadState  = 'waiting';
  vrBusy      = false;
  setListeningUI(true);
  setVrLabel('Hoere zu...');
  console.log('[VOICE] VAD gestartet');
  vrVadTick();
}

/* ── VAD tick (requestAnimationFrame loop) ────────────────────── */
function vrVadTick() {
  if (!vrActive) return;

  const buf = new Float32Array(vrAnalyser.fftSize);
  vrAnalyser.getFloatTimeDomainData(buf);
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  const rms = Math.sqrt(sum / buf.length);

  // Update VU bar
  const vuEl = document.getElementById('lb-interim');
  if (vuEl && vrVadState !== 'speaking') {
    const pct = Math.min(Math.round(rms / 0.15 * 100), 100);
    vuEl.textContent = rms > VAD_THRESHOLD ? '|'.repeat(Math.ceil(pct / 10)) : '';
  }

  const now      = Date.now();
  const isSpeech = rms > VAD_THRESHOLD;

  if (!vrBusy) {
    if (vrVadState === 'waiting') {
      if (isSpeech) {
        vrVadState    = 'speaking';
        vrSpeechStart = now;
        vrChunkStart();
        setVrLabel('Spreche...');
      }
    } else if (vrVadState === 'speaking') {
      if (!isSpeech) {
        vrVadState     = 'silence';
        vrSilenceStart = now;
      }
    } else if (vrVadState === 'silence') {
      if (isSpeech) {
        vrVadState = 'speaking';
      } else if (now - vrSilenceStart >= VAD_SILENCE_MS) {
        const spokenMs = vrSilenceStart - vrSpeechStart;
        if (spokenMs >= VAD_MIN_SPEAK_MS) {
          vrBusy = true;
          setVrLabel('Erkenne...');
          vrChunkStop();   // async, restarts loop when done
          return;
        } else {
          vrChunkAbort();
          vrVadState = 'waiting';
          setVrLabel('Hoere zu...');
        }
      }
    }
  }

  vrAnimFrame = requestAnimationFrame(vrVadTick);
}

/* ── MediaRecorder helpers ────────────────────────────────────── */
function vrChunkStart() {
  vrBlobs = [];
  try {
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus'
               : MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
    vrRecorder = new MediaRecorder(vrStream, mime ? { mimeType: mime } : {});
    vrMimeType = vrRecorder.mimeType || mime || 'audio/webm';
    vrRecorder.ondataavailable = e => { if (e.data && e.data.size > 0) vrBlobs.push(e.data); };
    vrRecorder.start(100);
  } catch (e) {
    console.error('[VOICE] MediaRecorder start failed:', e);
    vrVadState = 'waiting';
  }
}

function vrChunkAbort() {
  try { if (vrRecorder && vrRecorder.state !== 'inactive') vrRecorder.stop(); } catch {}
  vrBlobs    = [];
  vrRecorder = null;
}

async function vrChunkStop() {
  if (!vrRecorder || vrRecorder.state === 'inactive') {
    vrBusy = false; vrVadState = 'waiting'; setVrLabel('Hoere zu...'); vrVadTick(); return;
  }
  await new Promise(res => { vrRecorder.onstop = res; vrRecorder.stop(); });

  const blobs = [...vrBlobs];
  vrBlobs     = [];
  vrRecorder  = null;

  if (blobs.length > 0 && vrActive) {
    const blob = new Blob(blobs, { type: vrMimeType });
    console.log('[VOICE] Chunk:', blob.size, 'Bytes -> Flask');
    try {
      const resp = await fetch('/api/voice/transcribe', {
        method:  'POST',
        headers: { 'Content-Type': blob.type, 'X-Lang': vrLang },
        body:    blob,
      });
      const data = await resp.json();
      console.log('[VOICE] Antwort:', data);
      if (data.text && data.text.trim()) {
        const txt   = data.text.trim();
        const lower = txt.toLowerCase().replace(/[.,!?]/g, '').trim();
        const STOP_WORDS = ['stopp', 'stop', 'halt', 'abbrechen', 'aufhoeren', 'beenden'];
        if (STOP_WORDS.includes(lower)) {
          abortStream();
          console.log('[VOICE] Stream abgebrochen durch Sprache:', txt);
        } else if (!state.streaming) {
          const inp = document.getElementById('msg-input');
          inp.value = txt;
          autoResize(inp);
          // Mic bleibt aus (vrBusy=true) bis JARVIS fertig gesprochen hat
          sendMessage();
          vrVadState = 'waiting';
          if (vrActive) setVrLabel('Warte...');
          const vuElW = document.getElementById('lb-interim');
          if (vuElW) vuElW.textContent = '';
          return;   // frühes Return — vrBusy NICHT zurücksetzen
        } else {
          console.log('[VOICE] Streaming aktiv, Eingabe verworfen:', txt);
        }
      }
    } catch (e) {
      console.error('[VOICE] Fetch-Fehler:', e);
    }
  }

  vrBusy     = false;
  vrVadState = 'waiting';
  const vuEl2 = document.getElementById('lb-interim');
  if (vuEl2) vuEl2.textContent = '';
  if (vrActive) { setVrLabel('Hoere zu...'); vrVadTick(); }
}

/* ── Stop everything ─────────────────────────────────────────── */
function vrStop() {
  vrActive = false;
  if (vrAnimFrame) { cancelAnimationFrame(vrAnimFrame); vrAnimFrame = null; }
  vrChunkAbort();
  try { vrStream?.getTracks().forEach(t => t.stop()); } catch {}
  try { vrAudioCtx?.close(); } catch {}
  vrStream = vrAudioCtx = vrAnalyser = null;
  vrVadState = 'idle'; vrBusy = false;
  setListeningUI(false);
  setVrLabel('Hoere zu...');
  const i = document.getElementById('lb-interim'); if (i) i.textContent = '';
  console.log('[VOICE] Gestoppt');
}

// Alias fuer HTML cancel-Button
function cancelVoice() { vrStop(); }
function stopVoice()   { vrStop(); }

/* ── Sprache ─────────────────────────────────────────────────── */
function toggleLang() {
  vrLang = vrLang === 'de-DE' ? 'en-US' : 'de-DE';
  document.getElementById('lb-lang-btn').textContent = vrLang === 'de-DE' ? 'DE' : 'EN';
  showToast('Sprache: ' + (vrLang === 'de-DE' ? 'Deutsch' : 'English'));
}

function toggleAutoSend() {
  showToast('Auto-Senden immer AN (VAD-Modus)');
}

/* ── Fehler ──────────────────────────────────────────────────── */
function vrShowError(msg) {
  alert('Mikrofon:\n\n' + msg);
}


/* ── Hilfsfunktionen ───────────────────────────────────────────── */
function setVrLabel(text) {
  document.getElementById("lb-label").textContent = text;
}
function setVoiceDot(dotState) {
  const el = document.getElementById("voice-dot");
  if (el) el.className = "voice-dot " + dotState;
}
function setVoiceLabel(text) {
  const el = document.getElementById("voice-label");
  if (el) el.textContent = text;
}
function setListeningUI(on) {
  document.getElementById("listen-bar").style.display = on ? "flex" : "none";
  document.getElementById("mic-btn").classList.toggle("listening", on);
  if (on) {
    document.getElementById("lb-lang-btn").textContent = vrLang === "de-DE" ? "DE" : "EN";
    document.getElementById("lb-autosend-btn").classList.add("active");
  }
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2500);
}

/* ═══════════════════════ STATUS POLLING ════════════════════════
 * Pollt /api/status alle 15s: Internet, Claude, Token-Usage.
 * ════════════════════════════════════════════════════════════════ */
function formatTokens(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + "K";
  return n > 0 ? String(n) : "—";
}

function updateTokenDisplay(usage) {
  const tokEl = document.getElementById("m-tokens");
  if (!tokEl) return;
  const total = (usage.input || 0) + (usage.output || 0);
  tokEl.textContent = formatTokens(total);
}

async function pollStatus() {
  try {
    const data = await fetch("/api/status").then(r => r.json());
    const dotNet    = document.getElementById("dot-internet");
    const dotClaude = document.getElementById("dot-claude");
    if (dotNet)    dotNet.className    = "conn-dot " + (data.internet ? "online" : "offline");
    if (dotClaude) dotClaude.className = "conn-dot " + (data.claude   ? "online" : "offline");
    if (data.tokens) updateTokenDisplay(data.tokens);
  } catch { /* ignore */ }
}

pollStatus();
setInterval(pollStatus, 15_000);

/* ═══════════════════════ JARVIS STIMME (TTS) ════════════════════
 * Spielt Audio über AudioContext (bypasses Chrome autoplay-Sperre).
 * vrBusy=true während JARVIS spricht — Mic bleibt stumm.
 * ════════════════════════════════════════════════════════════════ */
let _ttsAudio   = null;   // HTMLAudioElement (Fallback)
let _ttsSource  = null;   // AudioBufferSourceNode (Hauptpfad)
let _ttsCtx     = null;   // eigener AudioContext (wenn kein vrAudioCtx)
let _ttsPending = false;  // true zwischen "spoken"-Event und Audio-Start

/* Gibt einen entsperrten AudioContext zurück.
 * Bevorzugt vrAudioCtx (bereits durch Mic-Klick entsperrt). */
function _getTtsCtx() {
  if (vrAudioCtx && vrAudioCtx.state !== 'closed') return vrAudioCtx;
  if (!_ttsCtx || _ttsCtx.state === 'closed') {
    try { _ttsCtx = new AudioContext(); } catch (e) { return null; }
  }
  return _ttsCtx;
}
// Context bei jedem User-Gesture entsperren (Enter, Klick, Touch)
['click', 'keydown', 'touchend'].forEach(ev =>
  document.addEventListener(ev, () => {
    const c = _getTtsCtx();
    if (c && c.state === 'suspended') c.resume().catch(() => {});
  }, { passive: true, capture: true })
);

async function playSpoken(text, id = "") {
  if (!text || !text.trim()) return;
  console.log('[TTS] playSpoken:', text.slice(0, 60));

  try {
    const wasActive = vrActive;
    if (wasActive) {
      vrBusy = true;
      if (document.getElementById('lb-label')) setVrLabel('JARVIS spricht...');
      setVoiceDot('connected');
    }

    // Laufendes Audio stoppen
    if (_ttsSource) { try { _ttsSource.stop(); } catch {} _ttsSource = null; }
    if (_ttsAudio)  { _ttsAudio.pause(); _ttsAudio = null; }

    console.log('[TTS] fetch start → /api/speak text:', text.slice(0, 30));
    let resp;
    try {
      resp = await fetch('/api/speak', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ text: text.trim(), id }),
      });
    } catch (fetchErr) {
      console.error('[TTS] fetch FEHLGESCHLAGEN:', fetchErr.name, fetchErr.message);
      throw fetchErr;
    }
    console.log('[TTS] fetch OK status:', resp.status, resp.ok);
    _ttsPending = false;

    if (!resp.ok) {
      console.warn('[TTS] Server-Fehler:', resp.status);
      if (wasActive) { vrBusy = false; vrVadTick(); }
      return;
    }

    const arrayBuffer = await resp.arrayBuffer();
    console.log('[TTS] arrayBuffer bytes:', arrayBuffer.byteLength);
    const ctx = _getTtsCtx();
    console.log('[TTS] AudioContext state:', ctx ? ctx.state : 'null');

    const _onEnd = () => {
      if (wasActive) {
        setTimeout(() => {
          vrBusy = false;
          if (document.getElementById('lb-label')) setVrLabel('Hoere zu...');
          setVoiceDot('listening');
          vrVadTick();
        }, 400);
      }
    };

    if (ctx && ctx.state !== 'closed') {
      // AudioContext-Pfad: kein Autoplay-Problem, funktioniert immer
      if (ctx.state === 'suspended') await ctx.resume();
      const audioBuf = await ctx.decodeAudioData(arrayBuffer);
      const source   = ctx.createBufferSource();
      source.buffer  = audioBuf;
      source.connect(ctx.destination);
      _ttsSource      = source;
      source.onended  = () => { _ttsSource = null; _onEnd(); };
      source.start();
      console.log('[TTS] spielt via AudioContext');
    } else {
      // Fallback: HTMLAudioElement (braucht frischen User-Gesture)
      const blob  = new Blob([arrayBuffer], { type: 'audio/mpeg' });
      const url   = URL.createObjectURL(blob);
      const audio = new Audio(url);
      _ttsAudio   = audio;
      audio.onended = () => { URL.revokeObjectURL(url); _ttsAudio = null; _onEnd(); };
      audio.onerror = (e) => {
        console.warn('[TTS] Audio-Fehler:', e);
        URL.revokeObjectURL(url); _ttsAudio = null;
        if (wasActive) { vrBusy = false; vrVadTick(); }
      };
      await audio.play();
      console.log('[TTS] spielt via HTMLAudio');
    }

  } catch (e) {
    _ttsPending = false;
    console.error('[TTS] CATCH:', e.name, '|', e.message, '|', e.stack);
    if (vrActive) {
      vrBusy = false;
      if (document.getElementById('lb-label')) setVrLabel('Hoere zu...');
      setVoiceDot('listening');
      vrVadTick();
    }
  }
}
