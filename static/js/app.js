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
  try {
    if (typeof marked.use === "function") {
      marked.use({ breaks: true, gfm: true });
    } else if (typeof marked.setOptions === "function") {
      marked.setOptions({ breaks: true, gfm: true });
    }
  } catch (e) {
    console.warn("[JARVIS] marked config fehlgeschlagen:", e);
  }
  vrInit();
  loadModels();   // Module-Status beim Start laden
  console.log("[JARVIS] init komplett");
});

/* ═══════════════════════ SATELLITE VIEW ═════════════════════════ */
let _satActive = false;

// Topbar SAT-Button
function toggleSatelliteModal() {
  _satActive ? deactivateSatView() : activateSatView();
}

// Logo-Bereich Toggle-Button
function toggleSatelliteView() {
  _satActive ? deactivateSatView() : activateSatView();
}

function activateSatView() {
  _satActive = true;
  const logo     = document.getElementById("rp-logo");
  const scanline = document.getElementById("rp-scanline");
  const map      = document.getElementById("jarvis-map");
  const ctrl     = document.getElementById("rp-sat-ctrl");
  const satBtn   = document.getElementById("sat-btn");
  const toggle   = document.getElementById("rp-sat-toggle");

  if (logo)     logo.style.display    = "none";
  if (scanline) scanline.style.display = "none";
  if (map)      map.style.display     = "block";
  if (ctrl)     ctrl.style.display    = "flex";
  if (satBtn)   satBtn.classList.add("active");
  if (toggle)   toggle.classList.add("active");

  // Leaflet initialisieren / Größe aktualisieren
  if (typeof L !== "undefined") {
    if (!window._leafletMap) {
      setTimeout(initLeafletMap, 120);
    } else {
      setTimeout(() => window._leafletMap.invalidateSize(), 120);
    }
  }
  showToast("Satelliten-Ansicht aktiviert");
}

function deactivateSatView() {
  _satActive = false;
  const logo     = document.getElementById("rp-logo");
  const scanline = document.getElementById("rp-scanline");
  const map      = document.getElementById("jarvis-map");
  const ctrl     = document.getElementById("rp-sat-ctrl");
  const satBtn   = document.getElementById("sat-btn");
  const toggle   = document.getElementById("rp-sat-toggle");

  if (logo)     logo.style.display    = "";
  if (scanline) scanline.style.display = "";
  if (map)      map.style.display     = "none";
  if (ctrl)     ctrl.style.display    = "none";
  if (satBtn)   satBtn.classList.remove("active");
  if (toggle)   toggle.classList.remove("active");
  showToast("Logo-Ansicht");
}

function _checkSatKeyword(text) {
  if (/satellit|satellite|sat[- ]?view|planet[- ]?view|weltall|orbit|karte|map\s/i.test(text)) {
    setTimeout(_showSatPrompt, 700);
  }
}

function _showSatPrompt() {
  if (_satActive) return;
  const msgArea = document.getElementById("messages");
  if (!msgArea || msgArea.style.display === "none") return;
  const ex = document.getElementById("sat-prompt-card");
  if (ex) ex.remove();

  const div = document.createElement("div");
  div.className = "message assistant";
  div.id = "sat-prompt-card";
  div.innerHTML = `
    <div class="msg-av jarvis">
      <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
        <polygon points="10,2 18,6.5 18,13.5 10,18 2,13.5 2,6.5" stroke="currentColor" stroke-width="1.5" fill="none"/>
        <circle cx="10" cy="10" r="2.5" fill="currentColor" opacity=".6"/>
      </svg>
    </div>
    <div class="msg-body">
      <span class="msg-name">JARVIS</span>
      <div class="msg-bubble">
        Soll ich die Satelliten-Ansicht aktivieren, Sir?
        <div style="display:flex;gap:8px;margin-top:10px">
          <button onclick="confirmSat(true)" class="sat-confirm-btn sat-yes">JA — AKTIVIEREN</button>
          <button onclick="confirmSat(false)" class="sat-confirm-btn sat-no">NEIN</button>
        </div>
      </div>
      <span class="msg-time">${ts()}</span>
    </div>`;
  msgArea.appendChild(div);
  scrollMessages();
}

function confirmSat(yes) {
  const card = document.getElementById("sat-prompt-card");
  if (card) card.remove();
  if (yes) activateSatView();
}

/* ═══════════════════════ KI-MODELL DROPDOWN (Topbar) ════════════ */
let _modelDropOpen   = false;
let _installInProgress = null;

function toggleModelDrop(e) {
  if (e) e.stopPropagation();
  _modelDropOpen ? closeModelDrop() : openModelDrop();
}

async function openModelDrop() {
  _modelDropOpen = true;
  const drop = document.getElementById("model-drop");
  const sel  = document.getElementById("tb-model-sel");
  if (!drop) return;
  drop.classList.add("open");
  if (sel) sel.classList.add("drop-open");

  try {
    const data   = await fetch("/api/models").then(r => r.json());
    const inner  = document.getElementById("model-drop-inner");
    if (!inner) return;

    // Topbar-Badge aktualisieren
    const active = data.models.find(m => m.active);
    _updateModelBadge(active);

    const ollama = data.ollama;
    inner.innerHTML = data.models.map(m => `
      <div class="mdc ${m.active ? "mdc-active" : ""}" id="mdc-${m.key}">
        <div class="mdc-head">
          <div class="mdc-tier-wrap">
            <span class="mdc-tier">T${m.tier}</span>
            ${m.installed ? '<span class="mdc-dot-ok">●</span>' : ''}
          </div>
          <div class="mdc-info">
            <span class="mdc-name">${m.id}</span>
            <span class="mdc-meta">${m.desc} · <span class="mdc-vram">${m.vram}</span></span>
          </div>
          <div class="mdc-action">
            ${m.active
              ? '<span class="mdc-badge-active">◉ AKTIV</span>'
              : m.installed
                ? `<button class="mdc-btn mdc-sel" onclick="selectModelDrop('${m.id}')">WÄHLEN</button>`
                : `<button class="mdc-btn mdc-inst" onclick="installModelDrop('${m.id}')"${!ollama ? ' disabled title="Ollama nicht installiert"' : ''}>LADEN</button>`
            }
          </div>
        </div>
        <div class="mdc-pbar-wrap" id="mdc-pb-${m.key}" style="display:none">
          <div class="mdc-pbar-track"><div class="mdc-pbar-fill" id="mdc-pf-${m.key}"></div></div>
          <span class="mdc-ptext" id="mdc-pt-${m.key}">Lade...</span>
        </div>
      </div>`).join("") +
      (!ollama ? '<div class="mdc-warn">Ollama nicht installiert — <a href="https://ollama.com" target="_blank" style="color:var(--cyan)">ollama.com</a></div>' : "");

  } catch(e) {
    const inner = document.getElementById("model-drop-inner");
    if (inner) inner.innerHTML = `<div class="mdc-warn" style="color:var(--danger)">Fehler: ${e.message}</div>`;
  }
}

function closeModelDrop() {
  _modelDropOpen = false;
  const drop = document.getElementById("model-drop");
  const sel  = document.getElementById("tb-model-sel");
  if (drop) drop.classList.remove("open");
  if (sel)  sel.classList.remove("drop-open");
}

function _updateModelBadge(active) {
  const nameEl = document.getElementById("tb-model-name");
  const dotEl  = document.getElementById("tb-model-dot");
  if (nameEl) nameEl.textContent = active ? active.key.toUpperCase() : "KI";
  if (dotEl)  dotEl.style.background = active ? "var(--accent)" : "var(--text-3)";
}

// Außerhalb klicken → schließen
document.addEventListener("click", (e) => {
  if (_modelDropOpen && !e.target.closest("#tb-model-sel") && !e.target.closest("#model-drop")) {
    closeModelDrop();
  }
});

async function loadModels() {
  try {
    const data = await fetch("/api/models").then(r => r.json());
    const active = data.models.find(m => m.active);
    _updateModelBadge(active);
  } catch {}
}

async function selectModelDrop(modelId) {
  try {
    const r = await fetch("/api/models/select", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelId }),
    });
    const d = await r.json();
    if (d.ok) { showToast(`Aktiv: ${modelId}`); closeModelDrop(); setTimeout(openModelDrop, 180); }
    else       showToast(`Fehler: ${d.error}`);
  } catch { showToast("Fehler beim Auswählen"); }
}

async function installModelDrop(modelId) {
  if (_installInProgress) { showToast("Installation läuft..."); return; }
  _installInProgress = modelId;

  const data = await fetch("/api/models").then(r => r.json()).catch(() => null);
  if (!data) { _installInProgress = null; return; }
  const m = data.models.find(x => x.id === modelId);
  if (!m)   { _installInProgress = null; return; }

  const prog  = document.getElementById(`mdc-pb-${m.key}`);
  const ptext = document.getElementById(`mdc-pt-${m.key}`);
  const pfill = document.getElementById(`mdc-pf-${m.key}`);
  if (prog)  prog.style.display  = "block";
  if (pfill) pfill.style.width   = "5%";

  try {
    const resp    = await fetch("/api/models/install", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelId }),
    });
    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let   buf     = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n"); buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.text) {
            if (ptext) ptext.textContent = ev.text.slice(0, 60);
            const pm = ev.text.match(/(\d+)%/);
            if (pm && pfill) pfill.style.width = pm[1] + "%";
          }
          if (ev.done) {
            if (pfill) pfill.style.width = "100%";
            showToast(`${modelId} bereit!`);
            setTimeout(() => { if (_modelDropOpen) openModelDrop(); }, 1000);
          }
          if (ev.error) {
            showToast(`Fehler: ${ev.error}`);
            if (prog) prog.style.display = "none";
          }
        } catch {}
      }
    }
  } catch(e) {
    showToast(`Fehler: ${e.message}`);
    if (prog) prog.style.display = "none";
  } finally {
    _installInProgress = null;
  }
}

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
  _checkSatKeyword(text);

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
      if (data.audio_b64) {
        playAudioBase64(data.audio_b64, data.mime || 'audio/mpeg');
      } else {
        playSpoken(data.text, data.id || "");
      }
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

/* ─── Feed helpers ────────────────────────────────────────────── */
function _feedAppend(card) {
  const feed = document.getElementById("activity-feed");
  document.getElementById("ap-empty").style.display = "none";
  feed.appendChild(card);
  feed.scrollTop = feed.scrollHeight;
}

function _sentenceForTool(tool, input) {
  const p = input || {};
  const fname = n => (n || "").split(/[/\\]/).pop();
  switch (tool) {
    case "read_file":        return `Liest Datei <span class="ac-file">${escHtml(fname(p.path))}</span>`;
    case "write_file":       return `Schreibt <span class="ac-file">${escHtml(fname(p.path))}</span>`;
    case "run_command":      return `Führt Befehl aus: <code>${escHtml((p.command||"").slice(0,70))}</code>`;
    case "list_directory":   return `Listet Ordner <span class="ac-file">${escHtml(fname(p.path)||p.path||"")}</span> auf`;
    case "search_files":     return `Sucht nach <span class="ac-file">${escHtml(p.pattern||"")}</span>`;
    case "browse_web":       return `Öffnet Webseite: <span class="ac-file">${escHtml((p.url||"").slice(0,60))}</span>`;
    case "web_click":        return `Klickt auf <code>${escHtml(p.selector||"")}</code>`;
    case "web_type":         return `Tippt in Feld: <code>${escHtml((p.text||"").slice(0,50))}</code>`;
    case "web_screenshot":   return `Erstellt Screenshot → <span class="ac-file">${escHtml(p.filename||"")}</span>`;
    case "web_scroll":       return `Scrollt Seite <span class="ac-file">${escHtml(p.direction||"down")}</span>`;
    case "web_get_links":    return `Sammelt alle Links der Seite`;
    case "web_navigate":     return `Navigation: <code>${escHtml(p.action||"")}</code>`;
    case "web_evaluate":     return `Führt JavaScript aus`;
    case "web_extract_table":return `Extrahiert Tabelle von der Seite`;
    case "download_file":    return `Lädt Datei herunter: <span class="ac-file">${escHtml((p.url||"").slice(0,50))}</span>`;
    case "search_web":       return `Sucht im Web: <em>${escHtml((p.query||"").slice(0,60))}</em>`;
    default:                 return `Tool <span class="ac-tool-name">${escHtml(tool)}</span> wird ausgeführt`;
  }
}

function _resultSummary(tool, result) {
  const r = (result || "").trim();
  if (!r) return "";
  const lines = r.split("\n").filter(l => l.trim());
  if (tool === "read_file" || tool === "write_file") {
    return lines.length > 1 ? `${lines.length} Zeilen` : r.slice(0, 80);
  }
  if (tool === "run_command") return lines[0].slice(0, 100);
  if (tool === "list_directory") return `${lines.length} Einträge`;
  return lines[0].slice(0, 90);
}

function addThinkingCard(text) {
  const card = document.createElement("div");
  card.className = "activity-card";
  card.innerHTML = `<div class="ac-sentence" style="color:var(--text-2);font-style:italic">${escHtml(text.slice(0, 200))}${text.length > 200 ? "…" : ""}</div>`;
  _feedAppend(card);
}

function addToolCard(data) {
  const card = document.createElement("div");
  card.className = "activity-card";
  card.id = `card-${data.tool_id}`;
  card.innerHTML = `
    <div class="ac-sentence">
      <span class="ac-tool-name">${(TOOL_META[data.tool]?.label || data.tool).toUpperCase()}</span>
      &nbsp;—&nbsp;${_sentenceForTool(data.tool, data.input)}
      <span class="ac-spinner" id="spin-${data.tool_id}"></span>
    </div>`;
  _feedAppend(card);
  state.toolCards[data.tool_id] = card;
}

function addAgentCard(data) {
  const agent = AGENT_META[data.agent_key] || { name: data.agent_key, color: "#888" };
  const task  = (data.input?.task || "").slice(0, 100);
  const card  = document.createElement("div");
  card.className = "activity-card";
  card.id = `card-${data.tool_id}`;
  card.style.borderColor = agent.color + "55";
  card.innerHTML = `
    <div class="ac-sentence">
      <span class="ac-agent" style="color:${agent.color}">${escHtml(agent.name)}</span>
      analysiert die Aufgabe<span class="ac-spinner" id="spin-${data.tool_id}"></span>
    </div>
    ${task ? `<div class="ac-result-line">${escHtml(task)}…</div>` : ""}`;
  _feedAppend(card);
  state.toolCards[data.tool_id] = card;
  state.agentKeys[data.tool_id] = data.agent_key;
  if (typeof window.activateAgentOrb === 'function') window.activateAgentOrb(data.agent_key);
}

function finishToolCard(data) {
  const card = state.toolCards[data.tool_id];
  if (!card) return;

  const spinner = card.querySelector(`#spin-${data.tool_id}`);
  if (spinner) spinner.replaceWith(Object.assign(document.createElement("span"), {
    className: "ac-status-ok", textContent: " ✓"
  }));

  const summary = _resultSummary(data.tool, data.result);
  if (summary) {
    const line = document.createElement("div");
    line.className = "ac-result-line";
    line.textContent = summary;
    card.appendChild(line);
  }

  card.style.borderColor = "rgba(0,229,160,.2)";
  const agentKey = state.agentKeys[data.tool_id];
  if (agentKey && typeof window.deactivateAgentOrb === 'function') window.deactivateAgentOrb(agentKey);
  document.getElementById("activity-feed").scrollTop = 99999;
}

function errorToolCard(data) {
  const card = state.toolCards[data.tool_id];
  if (!card) return;
  const spinner = card.querySelector(`#spin-${data.tool_id}`);
  if (spinner) spinner.replaceWith(Object.assign(document.createElement("span"), {
    className: "ac-status-err", textContent: " ✕"
  }));
  const line = document.createElement("div");
  line.className = "ac-result-line";
  line.style.borderColor = "rgba(244,63,94,.4)";
  line.style.color = "var(--danger)";
  line.textContent = (data.error || "Fehler").slice(0, 100);
  card.appendChild(line);
  card.style.borderColor = "rgba(244,63,94,.25)";
}

function addActivityCard(type, { label, preview }) {
  const card = document.createElement("div");
  card.className = "activity-card";
  card.innerHTML = `
    <div class="ac-sentence">${escHtml(label)}</div>
    ${preview ? `<div class="ac-result-line">${escHtml(preview)}</div>` : ""}`;
  _feedAppend(card);
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

const VAD_THRESHOLD    = 0.025;  // RMS-Schwelle
const VAD_SILENCE_MS   = 1200;   // 1.2s Stille → Aufnahme stoppen
const VAD_MIN_SPEAK_MS = 350;    // Mindest-Sprechdauer
const VAD_MAX_SPEAK_MS = 10000;  // Max 10s — verhindert endlose Aufnahmen

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

  if (!vrAudioCtx || vrAudioCtx.state === 'closed') {
    vrAudioCtx = new AudioContext();
  }
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
      // Max-Aufnahmezeit: Chunk erzwingen wenn zu lang (Rausch-Dauertrigger)
      if (now - vrSpeechStart >= VAD_MAX_SPEAK_MS) {
        vrBusy = true;
        setVrLabel('Erkenne...');
        vrChunkStop();
        return;
      }
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
  // vrAudioCtx bleibt offen — TTS-Wiedergabe funktioniert weiterhin
  try { if (vrAnalyser) vrAnalyser.disconnect(); } catch {}
  vrStream = vrAnalyser = null;
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
  updateCtxStats(usage);
  if (typeof window.updateSessionStats === 'function') window.updateSessionStats(usage);
}

/* ─ Kontext-Stats Block ─────────────────────────────────────────── */
const CTX_MAX      = 200000;   // Claude Sonnet 200k Kontext-Fenster
const CTX_COMPACT  = 160000;   // ~80% → Kompaktierung

function updateCtxStats(usage) {
  const lastCtx  = usage.last_ctx  || 0;
  const totalIn  = usage.input     || 0;
  const totalOut = usage.output    || 0;
  const reqs     = usage.requests  || 0;

  const ctxPct     = lastCtx > 0 ? Math.min(100, (lastCtx / CTX_MAX * 100))    : 0;
  const compactPct = lastCtx > 0 ? Math.min(100, (lastCtx / CTX_COMPACT * 100)) : 0;

  const ctxFill     = document.getElementById("ctx-fill");
  const compactFill = document.getElementById("compact-fill");
  const ctxPctEl    = document.getElementById("ctx-pct");
  const compactEl   = document.getElementById("compact-pct");
  const ctxInEl     = document.getElementById("ctx-in");
  const ctxOutEl    = document.getElementById("ctx-out");
  const ctxReqEl    = document.getElementById("ctx-req");

  if (ctxFill)     ctxFill.style.width     = ctxPct.toFixed(1) + "%";
  if (compactFill) compactFill.style.width  = compactPct.toFixed(1) + "%";
  if (ctxPctEl)    ctxPctEl.textContent     = ctxPct.toFixed(0) + "%";
  if (compactEl)   compactEl.textContent    = compactPct.toFixed(0) + "%";
  if (ctxInEl)     ctxInEl.textContent      = formatTokens(totalIn);
  if (ctxOutEl)    ctxOutEl.textContent     = formatTokens(totalOut);
  if (ctxReqEl)    ctxReqEl.textContent     = reqs || "—";

  // Farb-Warnung bei hohem Kontext
  if (ctxPctEl) ctxPctEl.style.color = ctxPct > 80 ? "var(--danger)" : ctxPct > 60 ? "#fbbf24" : "var(--cyan)";
  if (compactEl) compactEl.style.color = compactPct > 80 ? "var(--danger)" : compactPct > 60 ? "#fbbf24" : "var(--cyan)";
}

async function pollStatus() {
  try {
    const data = await fetch("/api/status").then(r => r.json());
    const dotNet    = document.getElementById("dot-internet");
    const dotClaude = document.getElementById("dot-claude");
    if (dotNet)    dotNet.className    = "tb-conn-dot " + (data.internet ? "online" : "offline");
    if (dotClaude) dotClaude.className = "tb-conn-dot " + (data.claude   ? "online" : "offline");
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

/* Spielt base64-kodiertes Audio direkt — kein separater Fetch nötig. */
async function playAudioBase64(b64, mime) {
  console.log('[TTS] base64 audio empfangen:', Math.round(b64.length * 0.75 / 1024) + ' KB');
  try {
    const wasActive = vrActive;
    if (wasActive) {
      vrBusy = true;
      if (document.getElementById('lb-label')) setVrLabel('JARVIS spricht...');
      setVoiceDot('connected');
    }
    if (_ttsSource) { try { _ttsSource.stop(); } catch {} _ttsSource = null; }
    if (_ttsAudio)  { _ttsAudio.pause(); _ttsAudio = null; }

    // base64 → ArrayBuffer (synchron, kein Fetch nötig)
    const bin = atob(b64);
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    const arrayBuffer = buf.buffer;

    const _onEnd = () => {
      // Mic nur freigeben wenn JARVIS fertig ist (kein laufender Stream)
      if (wasActive && !state.streaming) {
        setTimeout(() => {
          vrBusy = false;
          if (document.getElementById('lb-label')) setVrLabel('Hoere zu...');
          setVoiceDot('listening');
          vrVadTick();
        }, 400);
      }
    };

    const ctx = _getTtsCtx();
    if (ctx && ctx.state !== 'closed') {
      if (ctx.state === 'suspended') await ctx.resume();
      const audioBuf = await ctx.decodeAudioData(arrayBuffer);
      const source   = ctx.createBufferSource();
      source.buffer  = audioBuf;
      source.connect(ctx.destination);
      _ttsSource     = source;
      _ttsPending    = false;
      source.onended = () => { _ttsSource = null; _onEnd(); };
      source.start();
      console.log('[TTS] spielt via AudioContext');
    } else {
      // Fallback: data:-URL
      const url   = `data:${mime};base64,${b64}`;
      const audio = new Audio(url);
      _ttsAudio   = audio;
      _ttsPending = false;
      audio.onended = () => { _ttsAudio = null; _onEnd(); };
      audio.onerror = (e) => {
        console.warn('[TTS] Audio-Fehler:', e);
        _ttsAudio = null;
        if (wasActive) { vrBusy = false; vrVadTick(); }
      };
      await audio.play();
      console.log('[TTS] spielt via HTMLAudio data-URL');
    }
  } catch (e) {
    _ttsPending = false;
    console.error('[TTS] base64 CATCH:', e.name, '|', e.message);
    if (vrActive) {
      vrBusy = false;
      if (document.getElementById('lb-label')) setVrLabel('Hoere zu...');
      setVoiceDot('listening');
      vrVadTick();
    }
  }
}

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
      if (wasActive && !state.streaming) {
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
