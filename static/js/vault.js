/**
 * vault.js — JARVIS Obsidian Vault Widget
 * Canvas-Physik-Simulation, JARVIS HUD Style
 */

"use strict";

const VAULT_CFG = {
  api:          "/api/vault",
  fileApi:      "/api/vault/file",
  refreshMs:    30000,
  nodeRadius:   5,
  repulsion:    800,
  springLen:    55,
  springK:      0.04,
  damping:      0.82,
  centerPull:   0.012,
  edgeColor:    "rgba(0, 212, 255, 0.18)",
  edgeHover:    "rgba(0, 212, 255, 0.55)",
};

let vaultNodes   = [];
let vaultEdges   = [];
let hoveredNode  = null;
let animFrameId  = null;
let lastFrame    = 0;
let vaultCanvas  = null;
let vaultCtx     = null;
let isDragging   = false;
let dragNode     = null;

function initVault() {
  vaultCanvas = document.getElementById("vaultCanvas");
  if (!vaultCanvas) return;
  vaultCtx = vaultCanvas.getContext("2d");
  resizeVaultCanvas();

  vaultCanvas.addEventListener("mousemove",  onVaultMouseMove,  { passive: true });
  vaultCanvas.addEventListener("mouseleave", onVaultMouseLeave, { passive: true });
  vaultCanvas.addEventListener("mousedown",  onVaultMouseDown);
  vaultCanvas.addEventListener("mouseup",    onVaultMouseUp);
  vaultCanvas.addEventListener("click",      onVaultClick);
  window.addEventListener("resize", resizeVaultCanvas);

  fetchVaultData();
  setInterval(fetchVaultData, VAULT_CFG.refreshMs);
}

function resizeVaultCanvas() {
  if (!vaultCanvas) return;
  const rect = vaultCanvas.getBoundingClientRect();
  vaultCanvas.width  = rect.width  || 252;
  vaultCanvas.height = rect.height || 200;
}

async function fetchVaultData() {
  try {
    const res  = await fetch(VAULT_CFG.api);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Unknown error");
    buildGraph(data.nodes, data.edges);
    updateVaultBadge(data.total);
  } catch (err) {
    console.warn("[Vault] Fetch failed:", err);
  }
}

function buildGraph(rawNodes, rawEdges) {
  const W = vaultCanvas.width;
  const H = vaultCanvas.height;

  const posCache = {};
  vaultNodes.forEach(n => { posCache[n.id] = { x: n.x, y: n.y }; });

  vaultNodes = rawNodes.map(n => {
    const cached = posCache[n.id];
    return {
      ...n,
      x:  cached ? cached.x : W * 0.1 + Math.random() * W * 0.8,
      y:  cached ? cached.y : H * 0.1 + Math.random() * H * 0.8,
      vx: 0,
      vy: 0,
      r:  VAULT_CFG.nodeRadius + (n.ext === ".py" ? 1.5 : 0),
    };
  });

  const idxMap = {};
  vaultNodes.forEach((n, i) => { idxMap[n.id] = i; });

  vaultEdges = rawEdges
    .map(e => ({ si: idxMap[e.source] !== undefined ? idxMap[e.source] : -1, ti: idxMap[e.target] !== undefined ? idxMap[e.target] : -1 }))
    .filter(e => e.si >= 0 && e.ti >= 0);

  if (!animFrameId) {
    lastFrame  = performance.now();
    animFrameId = requestAnimationFrame(vaultLoop);
  }
}

function stepPhysics(dt) {
  const nodes = vaultNodes;
  const N     = nodes.length;
  const W     = vaultCanvas.width;
  const H     = vaultCanvas.height;
  const cx    = W / 2;
  const cy    = H / 2;

  for (let i = 0; i < N; i++) {
    for (let j = i + 1; j < N; j++) {
      const a  = nodes[i];
      const b  = nodes[j];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d2 = dx * dx + dy * dy + 1;
      const d  = Math.sqrt(d2);
      const f  = VAULT_CFG.repulsion / d2;
      const fx = f * dx / d;
      const fy = f * dy / d;
      a.vx -= fx;
      a.vy -= fy;
      b.vx += fx;
      b.vy += fy;
    }
  }

  for (const edge of vaultEdges) {
    const a  = nodes[edge.si];
    const b  = nodes[edge.ti];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const d  = Math.sqrt(dx * dx + dy * dy) || 1;
    const f  = (d - VAULT_CFG.springLen) * VAULT_CFG.springK;
    const fx = f * dx / d;
    const fy = f * dy / d;
    a.vx += fx;
    a.vy += fy;
    b.vx -= fx;
    b.vy -= fy;
  }

  const factor = dt / 16;
  for (const n of nodes) {
    if (n === dragNode) continue;
    n.vx += (cx - n.x) * VAULT_CFG.centerPull;
    n.vy += (cy - n.y) * VAULT_CFG.centerPull;
    n.vx *= VAULT_CFG.damping;
    n.vy *= VAULT_CFG.damping;
    n.x  += n.vx * factor;
    n.y  += n.vy * factor;
    n.x = Math.max(n.r + 2, Math.min(W - n.r - 2, n.x));
    n.y = Math.max(n.r + 2, Math.min(H - n.r - 2, n.y));
  }
}

function renderVault() {
  const ctx = vaultCtx;
  const W   = vaultCanvas.width;
  const H   = vaultCanvas.height;

  ctx.clearRect(0, 0, W, H);

  for (const edge of vaultEdges) {
    const a = vaultNodes[edge.si];
    const b = vaultNodes[edge.ti];
    const isHoverEdge = (a === hoveredNode || b === hoveredNode);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = isHoverEdge ? VAULT_CFG.edgeHover : VAULT_CFG.edgeColor;
    ctx.lineWidth   = isHoverEdge ? 1.2 : 0.7;
    ctx.stroke();
  }

  for (const n of vaultNodes) {
    const isHovered = n === hoveredNode;
    ctx.shadowColor = n.color;
    ctx.shadowBlur  = isHovered ? 14 : 4;
    ctx.beginPath();
    ctx.arc(n.x, n.y, isHovered ? n.r + 2 : n.r, 0, Math.PI * 2);
    ctx.fillStyle = isHovered ? n.color : hexAlpha(n.color, 0.75);
    ctx.fill();
    ctx.strokeStyle = n.color;
    ctx.lineWidth   = isHovered ? 1.5 : 0.8;
    ctx.stroke();
    ctx.shadowBlur  = 0;
  }
}

function vaultLoop(now) {
  const dt = Math.min(now - lastFrame, 64);
  lastFrame = now;
  stepPhysics(dt);
  renderVault();
  animFrameId = requestAnimationFrame(vaultLoop);
}

function getCanvasPos(e) {
  const rect = vaultCanvas.getBoundingClientRect();
  return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

function nodeAtPos(x, y) {
  for (let i = vaultNodes.length - 1; i >= 0; i--) {
    const n  = vaultNodes[i];
    const dx = n.x - x;
    const dy = n.y - y;
    if (dx * dx + dy * dy <= (n.r + 4) * (n.r + 4)) return n;
  }
  return null;
}

function onVaultMouseMove(e) {
  const pos = getCanvasPos(e);
  const hit = nodeAtPos(pos.x, pos.y);
  hoveredNode = hit;
  vaultCanvas.style.cursor = hit ? "pointer" : "default";

  const tip = document.getElementById("vaultTooltip");
  if (tip) {
    if (hit) {
      tip.textContent   = hit.path;
      tip.style.display = "block";
      tip.style.left    = (pos.x + 10) + "px";
      tip.style.top     = (pos.y - 28) + "px";
    } else {
      tip.style.display = "none";
    }
  }

  if (isDragging && dragNode) {
    dragNode.x  = pos.x;
    dragNode.y  = pos.y;
    dragNode.vx = 0;
    dragNode.vy = 0;
  }
}

function onVaultMouseLeave() {
  hoveredNode = null;
  isDragging  = false;
  dragNode    = null;
  const tip   = document.getElementById("vaultTooltip");
  if (tip) tip.style.display = "none";
}

function onVaultMouseDown(e) {
  const pos = getCanvasPos(e);
  const hit = nodeAtPos(pos.x, pos.y);
  if (hit) { isDragging = true; dragNode = hit; e.preventDefault(); }
}

function onVaultMouseUp() {
  isDragging = false;
  dragNode   = null;
}

function onVaultClick(e) {
  const pos = getCanvasPos(e);
  const hit = nodeAtPos(pos.x, pos.y);
  if (hit) openVaultFile(hit);
}

async function openVaultFile(node) {
  try {
    const res  = await fetch(VAULT_CFG.fileApi + "?path=" + encodeURIComponent(node.path));
    const data = await res.json();
    showVaultModal(node, data.ok ? data.content : ("// Error: " + data.error));
  } catch (err) {
    showVaultModal(node, "// Error loading file:\n// " + err.message);
  }
}

function showVaultModal(node, content) {
  let modal = document.getElementById("vaultModal");
  if (!modal) { modal = buildVaultModal(); document.body.appendChild(modal); }

  const title = modal.querySelector("#vaultModalTitle");
  const badge = modal.querySelector("#vaultModalBadge");
  const body  = modal.querySelector("#vaultModalBody");

  if (title) title.textContent = node.name;
  if (badge) {
    badge.textContent     = node.type.toUpperCase();
    badge.style.color     = node.color;
    badge.style.borderColor = node.color;
  }
  if (body) {
    body.innerHTML = content.split("\n").map((line, i) => {
      const num  = String(i + 1).padStart(4, " ");
      const safe = line.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      return '<span class="vm-line"><span class="vm-ln">' + num + "</span>" + safe + "</span>";
    }).join("\n");
  }

  modal.style.display = "flex";
  modal.onclick = function(e) { if (e.target === modal) modal.style.display = "none"; };
}

function buildVaultModal() {
  const m = document.createElement("div");
  m.id = "vaultModal";
  m.innerHTML = '<div class="vm-dialog"><div class="vm-header"><div class="vm-header-left"><span class="vm-icon">&#9672;</span><span id="vaultModalTitle" class="vm-title">FILE</span><span id="vaultModalBadge" class="vm-badge">PY</span></div><button class="vm-close" onclick="document.getElementById(\'vaultModal\').style.display=\'none\'">&#x2715;</button></div><pre id="vaultModalBody" class="vm-body"></pre></div>';
  return m;
}

function hexAlpha(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
}

function updateVaultBadge(total) {
  const badge = document.getElementById("vaultFileBadge");
  if (badge) badge.textContent = total;
}

document.addEventListener("DOMContentLoaded", initVault);
