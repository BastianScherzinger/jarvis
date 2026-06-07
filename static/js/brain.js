/* ═══════════════════════════════════════════════════════════════════
   JARVIS Brain.js — Three.js Neural Core + Background
   ═══════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ── Background particle field ──────────────────────────────────── */
  function initBackground(canvas) {
    if (!canvas || !window.THREE) return;
    const W = window.innerWidth, H = window.innerHeight;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020a14, 0.006);

    const cam = new THREE.PerspectiveCamera(60, W / H, 0.1, 300);
    cam.position.z = 90;

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: false, antialias: false });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setClearColor(0x020a14, 1);

    /* Stars */
    const starsGeo = new THREE.BufferGeometry();
    const sp = [];
    for (let i = 0; i < 2500; i++) {
      sp.push((Math.random() - 0.5) * 250, (Math.random() - 0.5) * 250, (Math.random() - 0.5) * 200);
    }
    starsGeo.setAttribute('position', new THREE.Float32BufferAttribute(sp, 3));
    const stars = new THREE.Points(starsGeo,
      new THREE.PointsMaterial({ color: 0x003355, size: 0.18, transparent: true, opacity: 0.7 }));
    scene.add(stars);

    /* Data helix streams */
    const hGeo = new THREE.BufferGeometry();
    const hp = [];
    for (let i = 0; i < 600; i++) {
      const t = (i / 600) * Math.PI * 24;
      const r = 50 + Math.random() * 30;
      hp.push(Math.cos(t) * r, (i / 600 - 0.5) * 120, Math.sin(t) * r);
    }
    hGeo.setAttribute('position', new THREE.Float32BufferAttribute(hp, 3));
    const helix = new THREE.Points(hGeo,
      new THREE.PointsMaterial({ color: 0x00d4ff, size: 0.1, transparent: true, opacity: 0.18 }));
    scene.add(helix);

    /* Floating bright nodes */
    const fnGeo = new THREE.BufferGeometry();
    const fn = [];
    for (let i = 0; i < 80; i++) {
      fn.push((Math.random() - 0.5) * 180, (Math.random() - 0.5) * 180, (Math.random() - 0.5) * 120);
    }
    fnGeo.setAttribute('position', new THREE.Float32BufferAttribute(fn, 3));
    const floatNodes = new THREE.Points(fnGeo,
      new THREE.PointsMaterial({ color: 0x00ffcc, size: 0.4, transparent: true, opacity: 0.45 }));
    scene.add(floatNodes);

    let t = 0;
    function animate() {
      requestAnimationFrame(animate);
      t += 0.0008;
      stars.rotation.y = t * 0.04;
      stars.rotation.x = t * 0.015;
      helix.rotation.y = t * 0.25;
      floatNodes.rotation.y = -t * 0.05;
      renderer.render(scene, cam);
    }
    animate();

    window.addEventListener('resize', () => {
      const W2 = window.innerWidth, H2 = window.innerHeight;
      cam.aspect = W2 / H2;
      cam.updateProjectionMatrix();
      renderer.setSize(W2, H2);
    });
  }

  /* ── Brain ──────────────────────────────────────────────────────── */
  let brainScene, brainCam, brainRenderer, brainPointsMesh;
  let allNodes = [];   // THREE.Vector3 array
  let memoryCount = 0;

  function initBrain(canvas) {
    if (!canvas || !window.THREE) return;

    const W = canvas.parentElement ? canvas.parentElement.clientWidth : 280;
    const H = W;

    brainScene = new THREE.Scene();
    brainCam = new THREE.PerspectiveCamera(50, 1, 0.1, 50);
    brainCam.position.z = 3.2;

    brainRenderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    brainRenderer.setSize(W, H);
    brainRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    brainRenderer.setClearColor(0x000000, 0);

    buildBrain(420);

    let t = 0;
    function animate() {
      requestAnimationFrame(animate);
      t += 0.004;
      if (brainPointsMesh) {
        brainPointsMesh.rotation.y = t * 0.28;
        brainPointsMesh.rotation.x = Math.sin(t * 0.09) * 0.12;
        const s = 1 + Math.sin(t * 0.7) * 0.018;
        brainPointsMesh.scale.setScalar(s);
      }
      brainRenderer.render(brainScene, brainCam);
    }
    animate();

    window.addEventListener('resize', () => {
      const canvas2 = document.getElementById('brain-canvas');
      if (!canvas2 || !brainRenderer) return;
      const size = canvas2.parentElement.clientWidth;
      brainCam.updateProjectionMatrix();
      brainRenderer.setSize(size, size);
    });
  }

  function buildBrain(count) {
    allNodes = [];
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      let r = 1.0
        + 0.18 * Math.sin(theta * 2) * Math.cos(phi * 3)
        + 0.10 * Math.sin(phi * 5)   * Math.cos(theta * 4)
        + 0.05 * Math.random();
      allNodes.push(new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta) * 0.82,
        r * Math.cos(phi)
      ));
    }
    rebuildMesh(false);
  }

  function rebuildMesh(flash) {
    if (brainPointsMesh) brainScene.remove(brainPointsMesh);
    /* clear all line segments */
    const toRemove = [];
    brainScene.traverse(obj => { if (obj.isLineSegments) toRemove.push(obj); });
    toRemove.forEach(obj => brainScene.remove(obj));

    const n = allNodes.length;
    const pos = [], col = [];

    for (let i = 0; i < n; i++) {
      const p = allNodes[i];
      pos.push(p.x, p.y, p.z);
      const isNew = flash && i >= n - 8;
      if (isNew) {
        col.push(1, 0.95, 0.3); /* yellow flash for new */
      } else {
        const cy = (p.y + 1) / 2;
        col.push(0, 0.35 + cy * 0.65, 0.6 + cy * 0.4);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('color',    new THREE.Float32BufferAttribute(col, 3));
    const mat = new THREE.PointsMaterial({ size: 0.045, vertexColors: true, transparent: true, opacity: 0.92 });
    brainPointsMesh = new THREE.Points(geo, mat);
    brainScene.add(brainPointsMesh);

    /* Connections */
    const lp = [], thresh = 0.34;
    let linkCount = 0;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        if (allNodes[i].distanceTo(allNodes[j]) < thresh) {
          lp.push(allNodes[i].x, allNodes[i].y, allNodes[i].z,
                  allNodes[j].x, allNodes[j].y, allNodes[j].z);
          linkCount++;
        }
      }
    }
    if (lp.length) {
      const lGeo = new THREE.BufferGeometry();
      lGeo.setAttribute('position', new THREE.Float32BufferAttribute(lp, 3));
      brainScene.add(new THREE.LineSegments(lGeo,
        new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.07 })));
    }

    /* Stats */
    const ne = document.getElementById('brain-nodes');
    const ce = document.getElementById('brain-conn');
    const me = document.getElementById('brain-mem');
    if (ne) ne.textContent = n;
    if (ce) ce.textContent = linkCount;
    if (me) me.textContent = memoryCount;
  }

  /* Public: grow brain on new message */
  window.brainGrow = function () {
    memoryCount++;
    const add = Math.floor(Math.random() * 6) + 5;
    for (let k = 0; k < add; k++) {
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      let r = 1.0
        + 0.18 * Math.sin(theta * 2) * Math.cos(phi * 3)
        + 0.10 * Math.sin(phi * 5)   * Math.cos(theta * 4)
        + 0.05 * Math.random();
      allNodes.push(new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta) * 0.82,
        r * Math.cos(phi)
      ));
    }
    rebuildMesh(true);
    setTimeout(() => rebuildMesh(false), 1400);

    /* Ripple effect on brain-wrap */
    const wrap = document.querySelector('.brain-wrap');
    if (wrap) {
      wrap.classList.add('pulse');
      setTimeout(() => wrap.classList.remove('pulse'), 800);
    }
  };

  /* Public: flash an agent color on the brain */
  window.brainFlashAgent = function (color) {
    const mat = brainPointsMesh && brainPointsMesh.material;
    if (!mat) return;
    /* brief color tint via a temporary point */
    const orig = mat.color.getHex();
    mat.color.set(color);
    setTimeout(() => mat.color.set(orig), 400);
  };

  /* ── Agent constellation ─────────────────────────────────────────── */
  const AGENT_META_B = {
    library:       { name: 'Library',    icon: '', color: '#a78bfa' },
    research:      { name: 'Research',   icon: '', color: '#38bdf8' },
    senior_dev:    { name: 'SeniorPy',   icon: '', color: '#34d399' },
    ux:            { name: 'UXCraft',    icon: '', color: '#fbbf24' },
    code_reviewer: { name: 'Review',     icon: '', color: '#60a5fa' },
    debugger:      { name: 'Debug',      icon: '', color: '#f87171' },
    bug_fixer:     { name: 'BugFix',     icon: '', color: '#fb923c' },
    bug_expert:    { name: 'BugWiz',     icon: '', color: '#c084fc' },
    performance:   { name: 'Speed',      icon: '', color: '#22d3ee' },
    security:      { name: 'Secure',     icon: '', color: '#f43f5e' },
  };

  function initConstellation() {
    const el = document.getElementById('agent-constellation');
    if (!el) return;
    el.innerHTML = '';
    Object.entries(AGENT_META_B).forEach(([key, meta]) => {
      const orb = document.createElement('div');
      orb.className = 'agent-orb';
      orb.id = 'orb-' + key;
      orb.style.setProperty('--c', meta.color);
      orb.innerHTML =
        '<div class="orb-glow"></div>' +
        '<div class="orb-ring"></div>' +
        '<div class="orb-body"><span>' + meta.name[0] + '</span></div>' +
        '<div class="orb-label">' + meta.name + '</div>';
      orb.title = meta.name;
      el.appendChild(orb);
    });
  }

  window.activateAgentOrb = function (agentKey) {
    const orb = document.getElementById('orb-' + agentKey);
    if (!orb) return;
    orb.classList.add('active');
    window.brainFlashAgent && window.brainFlashAgent(
      parseInt((AGENT_META_B[agentKey] || {color: '#00d4ff'}).color.slice(1), 16)
    );
  };
  window.deactivateAgentOrb = function (agentKey) {
    const orb = document.getElementById('orb-' + agentKey);
    if (orb) orb.classList.remove('active');
  };

  /* ── Clock ──────────────────────────────────────────────────────── */
  function startClock() {
    function tick() {
      const el = document.getElementById('m-time');
      if (el) el.textContent = new Date().toLocaleTimeString('de-DE');
    }
    tick();
    setInterval(tick, 1000);
  }

  /* ── Init ───────────────────────────────────────────────────────── */
  window.addEventListener('DOMContentLoaded', () => {
    initBackground(document.getElementById('bg-canvas'));
    initConstellation();
    startClock();
    setTimeout(() => initBrain(document.getElementById('brain-canvas')), 120);
  });

})();
