// EduNest – SMART ID SCAN (merged "Automated ID Card Enforcement System")
// Detects students who are not wearing their ID card, confirms their identity by face, and raises a
// violation that a teacher/admin reviews. Confirmed fines flow into the EduNest Fees page automatically.
//
// Three engines, one UI:
//   • Demo simulation  – runs entirely in the browser (no camera, no server).
//   • Server camera    – the backend reads a Hikvision / RTSP / USB camera and streams the annotated feed.
//   • Browser webcam   – this page sends webcam frames to the backend (like the original project's /process).
(() => {
  "use strict";

  // ---------------------------------------------------------------- icons / nav
  Object.assign(P, {
    idc: "M3 6h18v12H3zM7 10.5h5M7 14h3M15 10h2.5v3.5H15z",
    shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  });
  const after = NAV.findIndex(n => n[0] === "smart") >= 0 ? "smart" : "att";
  NAV.splice(NAV.findIndex(n => n[0] === after) + 1, 0, ["idscan", "ID Scan", "idc"]);

  // ---------------------------------------------------------------- state
  const DEF = {
    mode: "demo", url: (location.protocol==="http:"&&location.hostname?"http://"+location.hostname:"http://localhost")+":5000", token: "", fine: 50, hits: 2, review: true,
    running: false, t0: 0, sid: null, online: null, camOn: false, tab: "live", filter: "all",
    v: [], applied: {}, log: [], stats: { people: 0, ok: 0, no: 0 },
  };
  S.idc = Object.assign({}, DEF, S.idc || {});
  S.idc.camOn = false;
  if (S.idc.mode === "browser") S.idc.running = false;       // a reload always drops the webcam
  const c = () => S.idc;
  const isSrv = () => c().mode !== "demo";
  const base = () => c().url.replace(/\/+$/, "");
  const fmt = ms => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const fmtD = ms => new Date(ms).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  const mmss = ms => { const s = Math.max(0, Math.floor(ms / 1000)); return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); };
  const stu = id => ST.find(x => x.id === id);
  const forgetful = x => hs(x.id) % 3 === 0;                 // demo: these students often forget their card
  const STATUS = { pending: ["warn", "Pending review"], fined: ["bad", "Fined"], waived: ["ok", "Waived"] };

  // violations visible for the current engine (demo entries and server entries never mix on screen)
  const vis = () => c().v.filter(x => isSrv() ? x.src === "server" : x.src === "demo").sort((a, b) => b.ts - a.ts);
  const mine = () => c().v.filter(x => x.student_id === me.id).sort((a, b) => b.ts - a.ts);
  const snapURL = f => base() + "/api/id/snapshot/" + encodeURIComponent(f) + (c().token ? "?token=" + encodeURIComponent(c().token) : "");

  // ---------------------------------------------------------------- server helpers
  const hdr = () => Object.assign({ "Content-Type": "application/json" }, c().token ? { "X-Token": c().token } : {});
  const api = async path => { const r = await fetch(base() + path, { cache: "no-store", headers: hdr() }); if (!r.ok) throw new Error(r.status); return r.json(); };
  const post = async (path, body) => { const r = await fetch(base() + path, { method: "POST", headers: hdr(), body: JSON.stringify(body || {}) }); const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || r.status); return j; };

  // ---------------------------------------------------------------- fines <-> EduNest fees
  // A confirmed (fined) violation adds to the student's fee dues once; waiving it takes it back off.
  function syncFees() {
    const s = c();
    s.v.forEach(v => {
      const key = v.src + ":" + v.id, was = s.applied[key], f = S.fee && S.fee[v.student_id];
      if (!f) return;
      if (v.status === "fined" && was == null) {
        f.due += v.fine; s.applied[key] = v.fine;
        note(["parent", "admin"], v.name + " was fined " + money(v.fine) + " for not displaying an ID card (" + v.date + ")");
      } else if (v.status !== "fined" && was != null) {
        f.due = Math.max(0, f.due - was); delete s.applied[key];
        note(["parent", "admin"], "ID-card fine for " + v.name + " (" + v.date + ") was waived");
      }
    });
    s.v.length = Math.min(s.v.length, 400);
  }

  // ---------------------------------------------------------------- recognition events (demo engine + stage boxes)
  const flash = [];
  const todayStr = () => iso(0);
  function addLog(kind, name, sim, t) {
    const s = c();
    s.log.unshift({ t: t || Date.now(), kind, name, sim });
    s.log.length = Math.min(s.log.length, 40);
  }
  let dhits = {};
  function demoTick() {
    const s = c(); if (!s.running || isSrv()) return;
    const pool = Math.random() < .55 ? ST.filter(forgetful) : ST;      // the usual suspects turn up more often
    const x = pool[Math.floor(Math.random() * pool.length)];
    const noId = Math.random() < (forgetful(x) ? .8 : .04), sim = .66 + Math.random() * .3;
    flash.push({ n: x.n.split(" ")[0], ok: !noId, t: Date.now(), x: .06 + ((hs(x.id) * 7) % 60) / 100, y: .14 + ((hs(x.id) * 3) % 34) / 100, hits: 0 });
    if (!noId) addLog("id_ok", x.n, sim);
    else {
      const n = dhits[x.id] = (dhits[x.id] || 0) + 1;
      flash[flash.length - 1].hits = n;
      const exists = s.v.some(v => v.src === "demo" && v.student_id === x.id && v.date === todayStr() && v.status !== "waived");
      if (n >= s.hits && !exists) {
        s.v.unshift({ id: "d" + Date.now(), src: "demo", student_id: x.id, name: x.n, ts: Date.now() / 1000, date: todayStr(), similarity: sim, status: s.review ? "pending" : "fined", fine: +s.fine || 50, snapshot: "", note: "" });
        addLog("violation", x.n, sim); dhits[x.id] = 0; syncFees();
      } else addLog("no_id", x.n, sim);
    }
    const live = flash.filter(f => Date.now() - f.t < 4000);
    s.stats = { people: live.length, ok: live.filter(f => f.ok).length, no: live.filter(f => !f.ok).length };
    paint();
  }

  // ---------------------------------------------------------------- persistent stage (survives full redraws)
  const stage = document.createElement("div");
  stage.className = "sa-stage";
  stage.innerHTML = `<video muted playsinline></video><img alt="Annotated ID scan feed"><canvas width="1280" height="720"></canvas>
    <div class="sa-idle"><div class="big"><svg class="ic" viewBox="0 0 24 24"><path d="${P.idc}"/></svg></div><b>Camera idle</b><span class="sm">Start scanning to check for ID cards</span></div>
    <div class="sa-hud"><i class="c tl"></i><i class="c tr"></i><i class="c bl"></i><i class="c br"></i><span class="scanline"></span><span class="sa-rec">SCANNING</span><span class="sa-src"></span></div>`;
  const vid = stage.querySelector("video"), img = stage.querySelector("img"), cv = stage.querySelector("canvas"), g = cv.getContext("2d");
  img.addEventListener("error", () => { img.style.display = "none"; });

  function attach() {
    const slot = document.getElementById("id-slot");
    if (!slot) return;
    if (stage.parentNode !== slot) slot.appendChild(stage);
    syncStage();
    if (vid.srcObject && vid.paused) vid.play().catch(() => {});
  }
  window.__afterDraw.push(attach);

  function syncStage() {
    const s = c(), on = s.running;
    stage.classList.toggle("on", on);
    stage.querySelector(".sa-idle").style.display = on ? "none" : "flex";
    stage.querySelector(".sa-src").textContent = s.mode === "demo" ? "Demo · simulated feed" : s.mode === "server" ? "ID Scan · " + base().replace(/^https?:\/\//, "") : "ID Scan · browser webcam";
    vid.style.display = s.mode === "browser" && s.camOn ? "block" : "none";
    if (s.mode === "server" && on && s.online) {
      const u = base() + "/api/id/video_feed" + (s.token ? "?token=" + encodeURIComponent(s.token) : "");
      if (img.dataset.u !== u) { img.dataset.u = u; img.src = u + (u.includes("?") ? "&" : "?") + "t=" + Date.now(); }
      img.style.display = "block";
    } else if (s.mode !== "browser" || !on) { img.removeAttribute("src"); img.dataset.u = ""; img.style.display = "none"; }
  }

  // ---------------------------------------------------------------- canvas overlay (demo engine only)
  function corners(x, y, w, h, col) {
    g.strokeStyle = col; g.lineWidth = 4; const L = 26;
    [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]].forEach(([cx, cy, dx, dy]) => {
      g.beginPath(); g.moveTo(cx, cy + dy * L); g.lineTo(cx, cy); g.lineTo(cx + dx * L, cy); g.stroke();
    });
  }
  function tag(text, x, y, col) {
    g.font = "600 24px Inter, system-ui, sans-serif";
    const w = g.measureText(text).width + 24;
    g.fillStyle = col; g.beginPath(); g.roundRect ? g.roundRect(x, y - 38, w, 34, 17) : g.rect(x, y - 38, w, 34); g.fill();
    g.fillStyle = "#fff"; g.fillText(text, x + 12, y - 14);
  }
  let dirty = false;
  function render() {
    requestAnimationFrame(render);
    const W = cv.width, H = cv.height, now = Date.now(), s = c();
    if (!stage.isConnected || !s.running || isSrv()) { if (dirty) { g.clearRect(0, 0, W, H); dirty = false; } return; }
    dirty = true; g.clearRect(0, 0, W, H);
    g.strokeStyle = "#ffffff0d"; g.lineWidth = 1;
    for (let x = 0; x < W; x += 64) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); }
    for (let y = 0; y < H; y += 64) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
    flash.filter(f => now - f.t < 3200).forEach(f => {
      const a = 1 - (now - f.t) / 3200, x = f.x * W, y = f.y * H, col = f.ok ? "#3ee8a5" : "#ff9a3c";
      g.globalAlpha = Math.min(1, a * 1.6);
      g.fillStyle = col + "1a"; g.fillRect(x, y, 170, 300);
      corners(x, y, 170, 300, col);
      g.fillStyle = col + "55"; g.beginPath(); g.arc(x + 85, y + 80, 34, 0, 7); g.fill(); g.fillRect(x + 35, y + 125, 100, 150);
      if (f.ok) { g.fillStyle = "#4aa3ff"; g.fillRect(x + 62, y + 150, 46, 62); }           // the ID card on the chest
      tag(f.ok ? f.n + " · ID verified" : f.n + " · NO ID " + Math.min(f.hits, c().hits) + "/" + c().hits, x, y, f.ok ? "#17a673" : "#e0731a");
      g.globalAlpha = 1;
    });
  }
  requestAnimationFrame(render);

  // ---------------------------------------------------------------- engines
  let demoT = null, pollBusy = false, loopT = null, busy = false, errShown = false;
  const work = document.createElement("canvas");
  const startDemo = () => { clearInterval(demoT); demoT = setInterval(demoTick, 800); };
  const stopDemo = () => clearInterval(demoT);

  async function startBrowser() {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera needs https:// or localhost");
    vid.srcObject = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: 1280, height: 720 }, audio: false });
    await vid.play(); c().camOn = true;
    clearInterval(loopT); errShown = false; loopT = setInterval(sendFrame, 900);
  }
  function stopBrowser() {
    clearInterval(loopT); (vid.srcObject?.getTracks() || []).forEach(t => t.stop()); vid.srcObject = null; c().camOn = false;
    img.removeAttribute("src"); img.style.display = "none";
  }
  async function sendFrame() {
    const s = c();
    if (busy || !s.running || !vid.videoWidth) return;
    busy = true;
    try {
      const w = Math.min(960, vid.videoWidth), h = Math.round(w * vid.videoHeight / vid.videoWidth);
      work.width = w; work.height = h; work.getContext("2d").drawImage(vid, 0, 0, w, h);
      const r = await post("/api/id/frame", { image: work.toDataURL("image/jpeg", .7) });
      s.online = true;
      if (r.processed_image) { img.src = "data:image/jpeg;base64," + r.processed_image; img.style.display = "block"; }
      errShown = false;
    } catch (e) {
      if (!errShown) { errShown = true; toast("Frame rejected: " + e.message); }
    } finally { busy = false; }
  }

  async function pull() {
    const s = c(), team = isT();
    const d = await api("/api/id/violations" + (team ? "" : "?student_id=" + encodeURIComponent(me.id)));
    s.v = s.v.filter(x => x.src !== "server").concat(d.violations.map(x => Object.assign({}, x, { src: "server" })));
    syncFees();
  }
  async function poll() {
    const s = c();
    if (pollBusy || !isSrv()) return;
    if (S.view !== "idscan" && !s.running) return;
    pollBusy = true;
    try {
      if (isT()) {
        const d = await api("/api/id/status"), was = s.online; s.online = true;
        if (s.mode === "server") {
          if (d.running) { if (d.session_id !== s.sid) { s.sid = d.session_id; s.t0 = (d.started_at || Date.now() / 1000) * 1000; } s.running = true; }
          else if (s.running) { s.running = false; toast("Server stopped the scan"); }
        }
        s.stats = { people: d.stats.people, ok: d.stats.id_ok, no: d.stats.no_id };
        s.log = (d.recent || []).map(e => ({ t: e.t * 1000, kind: e.kind, name: e.name, sim: e.sim }));
        await pull();
        if (!was) draw(); else { syncStage(); paint(); }
      } else { await pull(); s.online = true; paint(); }
    } catch (e) {
      if (s.online !== false) { s.online = false; syncStage(); draw(); } else paint();
    } finally { pollBusy = false; }
  }
  setInterval(poll, 2000);

  // ---------------------------------------------------------------- views
  const ico = n => ic(n).replace('class="ic"', 'class="ic" style="vertical-align:-4px;margin-right:6px"');
  const chip = st => `<span class="id-chip ${STATUS[st][0]}">${STATUS[st][1]}</span>`;

  const stateHTML = () => {
    const s = c(), srv = isSrv();
    return `<span class="sa-pill ${s.running ? "on" : ""}"><i class="sa-dot"></i>${s.running ? `Scanning · <span id="id-time">${mmss(Date.now() - s.t0)}</span>` : "Idle"}</span>` +
      (srv ? `<span class="sa-pill ${s.online ? "on" : s.online === false ? "err" : ""}"><i class="sa-dot"></i>${s.online ? "Server online" : s.online === false ? "Server unreachable" : "Connecting…"}</span>` : `<span class="sa-pill"><i class="sa-dot"></i>Demo engine</span>`);
  };
  const statsHTML = () => {
    const s = c(), pend = vis().filter(x => x.status === "pending").length, box = (cls, i, v, l) => `<div class="card sa-stat ${cls}"><div class="ico">${ic(i)}</div><div><div class="stat gh">${v}</div><div class="mute sm">${l}</div></div></div>`;
    return box("p", "check", s.stats.ok, "ID verified in view") + box("b", "idc", s.stats.no, "Without ID in view") + box("l", "clock", pend, "Pending review") + box("", "wallet", money(vis().filter(x => x.status === "fined").reduce((a, x) => a + x.fine, 0)), "Fines confirmed");
  };
  const actions = v => {
    if (!isT()) return "";
    const b = (a, label, cls) => `<button class="btn ${cls} s" data-a="idrev" data-i="${v.id}" data-k="${a}">${label}</button>`;
    return `<div class="id-act">${v.status === "pending" ? b("confirm", "Confirm fine", "") + b("waive", "Waive", "alt") : v.status === "fined" ? b("waive", "Waive", "alt") : b("confirm", "Fine anyway", "alt")}</div>`;
  };
  const vRow = (v, showAct = true) => {
    const x = stu(v.student_id) || { id: v.student_id, n: v.name };
    const pic = v.snapshot && v.src === "server" && isT() ? `<img class="id-snap" src="${esc(snapURL(v.snapshot))}" alt="Snapshot" loading="lazy">` : face(x, 42);
    return `<div class="id-v ${v.status}"><div class="id-pic">${pic}</div><div class="sa-who"><b>${esc(v.name)}</b><span class="mute sm">${esc(v.student_id)} · ${fmtD(v.ts * 1000)}${v.similarity && isT() ? " · match " + Math.round(v.similarity * 100) + "%" : ""}</span></div><div class="id-end">${chip(v.status)}<span class="mute sm">${money(v.fine)}</span></div>${showAct ? actions(v) : ""}</div>`;
  };
  const todayList = () => {
    const l = vis().filter(x => x.date === todayStr());
    return l.map(v => vRow(v)).join("") || '<span class="mute sm">No ID-card violations today.</span>';
  };
  const logText = e => e.kind === "id_ok" ? `<b>${esc(e.name)}</b> · ID verified` : e.kind === "violation" ? `<b>${esc(e.name)}</b> · <span class="tag bad">violation raised</span>` : e.kind === "error" ? `<span class="tag bad">${esc(e.name)}</span>` : `<b>${esc(e.name)}</b> · no ID card seen${e.sim ? " · face match " + Math.round(e.sim * 100) + "%" : ""}`;
  const logHTML = () => c().log.map(e => `<div class="sa-ev"><time>${fmt(e.t)}</time><span>${logText(e)}</span></div>`).join("") || '<span class="mute sm">Detections appear here in real time.</span>';

  function paint() {
    const set = (id, h) => { const e = document.getElementById(id); if (e) e.innerHTML = h; };
    set("id-stats", statsHTML()); set("id-today", todayList()); set("id-log", logHTML()); set("id-state", stateHTML());
  }
  setInterval(() => { const e = document.getElementById("id-time"); if (e && c().running) e.textContent = mmss(Date.now() - c().t0); }, 1000);

  V.idscan = () => isT() ? idT() : idS();

  function idT() {
    const s = c(), tab = s.tab;
    const tabs = [["live", "Live scan"], ["viol", "Violations"], ["ledger", "Fines by student"], ["setup", "Setup & rules"]].map(t => `<button class="pill ${tab === t[0] ? "on" : ""}" data-a="idtab" data-i="${t[0]}">${t[1]}</button>`).join("");
    return `<div class="hero sa-hero"><div><span class="eyebrow">ID card compliance</span><h1>Smart ID Scan</h1><p>Cameras spot students without an ID card, confirm who they are, and queue a fine for your review.</p></div><div class="sa-state" id="id-state">${stateHTML()}</div></div>
    <div class="tabs">${tabs}</div>` + (tab === "live" ? liveTab() : tab === "viol" ? violTab() : tab === "ledger" ? ledgerTab() : setupTab());
  }

  function liveTab() {
    const s = c(), srv = isSrv();
    const hint = s.mode === "demo" ? "Demo mode simulates a gate camera in your browser. Some students “forget” their card so you can try the review flow."
      : s.mode === "server" ? "The backend reads its own camera and streams the annotated feed here. Face matches use the Smart Attendance face database."
        : "Your webcam frames are sent to the backend for analysis (about one per second). Good for testing with a laptop.";
    return `<div class="grid sa-stats" id="id-stats">${statsHTML()}</div>
    <div class="sa-layout"><div>
      <div class="card"><div class="seg">${[["demo", "Demo simulation"], ["server", "Server camera"], ["browser", "Browser webcam"]].map(m => `<button class="${s.mode === m[0] ? "on" : ""}" data-a="idmode" data-i="${m[0]}">${m[1]}</button>`).join("")}</div>
        <div id="id-slot"></div>
        <div class="sa-btns">${s.running ? '<button class="btn bad" data-a="idstop">Stop scanning</button>' : `<button class="btn" data-a="idstart">${ico("idc")}Start scanning</button>`}
          <span class="mute sm" style="flex:1;min-width:180px">${hint}</span></div>
        ${srv && s.online === false ? `<p class="sm" style="color:var(--bad);margin:10px 0 0">Can't reach ${esc(s.url)}. Start the backend (see <b>Setup &amp; rules</b>) or switch to Demo.</p>` : ""}</div>
      <div class="card"><h2>Live activity</h2><div class="sa-log" id="id-log">${logHTML()}</div></div>
    </div>
    <div class="card"><div class="row sp"><h2>Today's violations</h2><span class="tag">${money(s.fine)} per violation</span></div><div class="id-list" id="id-today">${todayList()}</div>
      <p class="sm mute" style="margin:10px 0 0">${s.review || srv ? "Nothing is charged until you confirm it. Confirmed fines are added to the student's Fees page and the parent is notified." : "Auto-fine is on: violations are charged immediately."}</p></div></div>`;
  }

  function violTab() {
    const s = c(), all = vis(), list = all.filter(x => s.filter === "all" || x.status === s.filter);
    const pills = [["all", "All"], ["pending", "Pending"], ["fined", "Fined"], ["waived", "Waived"]].map(t => `<button class="pill ${s.filter === t[0] ? "on" : ""}" data-a="idfilt" data-i="${t[0]}">${t[1]} ${t[0] === "all" ? all.length : all.filter(x => x.status === t[0]).length}</button>`).join("");
    return `<div class="card"><div class="row sp"><div class="tabs" style="margin:0">${pills}</div><button class="btn alt s" data-a="idexport" ${all.length ? "" : "disabled"}>${ico("dl")}Export CSV</button></div>
      <div class="id-list" style="margin-top:12px">${list.map(v => vRow(v)).join("") || '<span class="mute">Nothing here yet. Run a scan from the Live tab.</span>'}</div></div>`;
  }

  function ledgerTab() {
    const by = {};
    vis().forEach(v => { const e = by[v.student_id] = by[v.student_id] || { id: v.student_id, n: v.name, k: 0, amt: 0, p: 0 }; if (v.status === "fined") { e.k++; e.amt += v.fine; } else if (v.status === "pending") e.p++; });
    const rows = Object.values(by).sort((a, b) => b.amt - a.amt || b.p - a.p);
    const tot = rows.reduce((a, r) => a + r.amt, 0);
    return `<div class="card"><div class="row sp"><h2>Fines by student</h2><span class="tag ${tot ? "bad" : "ok"}">${money(tot)} confirmed</span></div>
      ${rows.map(r => `<div class="stu">${face(stu(r.id) || { id: r.id, n: r.n }, 44)}<div style="flex:1"><b>${esc(r.n)}</b><div class="mute sm">${r.id}</div></div><span class="tag ${r.k ? "bad" : ""}">${r.k} fined</span>${r.p ? `<span class="tag warn">${r.p} pending</span>` : ""}<b style="min-width:72px;text-align:right">${money(r.amt)}</b></div>`).join("") || '<span class="mute">No violations recorded yet.</span>'}
      <p class="sm mute" style="margin:10px 0 0">These amounts are already included in each student's dues on the <b>Fees</b> page.</p></div>`;
  }

  function setupTab() {
    const s = c();
    return `<div class="card"><h2>How it works</h2><div class="sa-flow"><div><b>1 · Detect</b>YOLO finds every person in frame</div><span>›</span><div><b>2 · ID check</b>A second model looks for the ID card</div><span>›</span><div><b>3 · Identify</b>No card? InsightFace matches the face</div><span>›</span><div><b>4 · Confirm</b>Seen without ID several times, not just once</div><span>›</span><div><b>5 · Review</b>Teacher confirms or waives; fee is updated</div></div></div>
    <div class="card"><h2>Backend connection</h2><div class="row"><input class="in" id="id-url" style="flex:2;min-width:220px" value="${esc(s.url)}" placeholder="http://localhost:5000" data-idc="url"><input class="in" id="id-token" type="password" style="flex:1;min-width:160px" value="${esc(s.token)}" placeholder="API token (if set)" data-idc="token" autocomplete="off"><button class="btn alt" data-a="idtest">${ico("plug")}Test connection</button></div>
      <p class="sm mute">Smart ID Scan shares the server with Smart Attendance (same URL, endpoints under <code>/api/id</code>). Open EduNest from <b>http://localhost</b>; an https page cannot call an http server.</p>
      <h2 style="margin-top:14px">Start the backend</h2>
      <div class="code">cd backend
pip install -r requirements.txt

# try everything with no camera and no AI models:
DEMO_MODE=1 python app.py

# real detection (needs the face DB from db_make.py, same as Smart Attendance):
CAMERA_MODE=webcam CAMERA_URL=0 python app.py
# optional: ID_FINE_AMOUNT=50  ID_AUTO_CONFIRM=0  ID_API_TOKEN=choose-a-secret</div></div>
    <div class="card"><h2>Rules <span class="tag">demo engine</span></h2><p class="sm mute">With a real server these come from environment variables (<code>ID_FINE_AMOUNT</code>, <code>ID_CONFIRM_HITS</code>, <code>ID_AUTO_CONFIRM</code>).</p>
      <div class="row"><label class="sm">Fine per violation (₹)</label><input class="in" type="number" min="0" style="width:100px" value="${s.fine}" data-idc="fine"><label class="sm">Sightings before a violation</label><input class="in" type="number" min="1" max="10" style="width:80px" value="${s.hits}" data-idc="hits"></div>
      <label class="id-check"><input type="checkbox" ${s.review ? "checked" : ""} data-idc="review"> Require teacher review before a fine counts <span class="mute sm">(recommended: face matching is never perfect)</span></label></div>
    <div class="card"><h2>${ico("shield")}Privacy &amp; fairness</h2><ul class="id-list-plain sm"><li>Get written consent and follow your school's data policy before enrolling faces or fining students.</li><li>Violation snapshots stay on the school server (<code>backend/id_data/snapshots</code>) and are visible to staff only. Students and parents see the date and amount, never the image.</li><li>Keep the review step on, and waive anything doubtful. Lighting, masks and look-alikes cause mismatches.</li><li>Delete old snapshots on a schedule that matches your retention policy.</li></ul></div>`;
  }

  function idS() {
    const l = mine(), fined = l.filter(x => x.status === "fined"), pend = l.filter(x => x.status === "pending"), amt = fined.reduce((a, x) => a + x.fine, 0);
    return head("Smart ID Scan", "Your ID-card record") +
      `<div class="card sa-banner"><div class="t"><div class="ico">${ic("idc")}</div><div><h2 style="margin:0">Wear your ID card every day</h2><div class="mute sm">Gate cameras check for visible ID cards. A teacher reviews every case before any fine is applied.</div></div></div><span class="tag ${fined.length ? "bad" : pend.length ? "warn" : "ok"}">${fined.length ? fined.length + " fine" + (fined.length > 1 ? "s" : "") + " · " + money(amt) : pend.length ? pend.length + " under review" : "All clear"}</span></div>
      <div class="card"><h2>History</h2>${l.map(v => vRow(v, false)).join("") || '<span class="mute">No ID-card violations. Keep it up!</span>'}</div>
      <p class="sm mute">Think a fine is a mistake? Ask your class teacher to review it. Fines appear in <b>Fees</b> once confirmed.</p>`;
  }

  // teacher/admin home: one-glance compliance card
  const baseDash = V.dash;
  V.dash = () => {
    const h = baseDash();
    if (!isT()) return h;
    const l = vis().filter(x => x.date === todayStr()), p = l.filter(x => x.status === "pending").length;
    return h + `<div class="card sa-banner"><div class="t"><div class="ico">${ic("idc")}</div><div><h2 style="margin:0">ID-card compliance today</h2><div class="mute sm">${l.length ? l.length + " violation" + (l.length > 1 ? "s" : "") + (p ? " · " + p + " waiting for your review" : " · all reviewed") : "No violations recorded"}</div></div></div><button class="btn" data-a="go" data-i="idscan">Open Smart ID Scan</button></div>`;
  };

  // ---------------------------------------------------------------- actions
  Object.assign(A, {
    idtab: i => { c().tab = i; },
    idfilt: i => { c().filter = i; },
    idmode: i => { const s = c(); if (s.running) return toast("Stop scanning first"); s.mode = i; s.online = null; syncStage(); if (i !== "demo") poll(); },
    idstart: async () => {
      const s = c();
      try {
        if (s.mode === "server") { const r = await post("/api/id/start", { source: "server" }); s.sid = r.session_id; s.online = true; }
        else if (s.mode === "browser") { await post("/api/id/start", { source: "browser" }); s.online = true; await startBrowser(); }
      } catch (e) {
        if (s.mode === "browser") stopBrowser();
        s.online = s.online === true ? true : false; draw();
        return toast("Could not start: " + (e.message || "server unreachable"));
      }
      s.running = true; s.t0 = Date.now(); s.log = []; dhits = {}; flash.length = 0;
      if (s.mode === "demo") startDemo();
      syncStage(); toast("ID scanning started"); draw();
    },
    idstop: async () => {
      const s = c();
      if (s.mode !== "demo") { try { await post("/api/id/stop"); } catch (e) { /* server may already be stopped */ } }
      s.running = false; stopDemo(); stopBrowser(); syncStage(); toast("Scanning stopped"); draw();
    },
    idrev: async (id, k) => {
      const v = c().v.find(x => x.id === id); if (!v) return;
      if (v.src === "server") {
        try { await post("/api/id/violations/" + encodeURIComponent(id) + "/review", { action: k }); await pull(); }
        catch (e) { return toast("Could not reach the server: " + e.message); }
      } else { v.status = k === "confirm" ? "fined" : "waived"; syncFees(); }
      toast(k === "confirm" ? "Fine confirmed · added to " + v.name.split(" ")[0] + "'s fees" : "Violation waived"); draw();
    },
    idexport: () => {
      const rows = [["Student ID", "Name", "Date", "Time", "Match", "Status", "Fine"]];
      vis().forEach(v => rows.push([v.student_id, v.name, v.date, fmt(v.ts * 1000), v.similarity ? Math.round(v.similarity * 100) + "%" : "", STATUS[v.status][1], v.fine]));
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([rows.map(r => r.map(x => '"' + String(x).replace(/"/g, '""') + '"').join(",")).join("\n")], { type: "text/csv" }));
      a.download = "id-violations-" + iso(0) + ".csv"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    },
    idtest: async () => {
      const s = c(); s.online = null;
      try { const d = await (await fetch(base() + "/api/id/health", { cache: "no-store" })).json(); s.online = true; toast("Connected" + (d.demo ? " · server is in DEMO mode" : "") + (d.token_required && !s.token ? " · token required" : "")); }
      catch (e) { s.online = false; toast("Could not reach " + s.url); }
    },
  });
  document.addEventListener("change", e => {
    const t = e.target, k = t.dataset && t.dataset.idc, s = c();
    if (!k) return;
    if (k === "url") { s.url = t.value.trim() || DEF.url; s.online = null; }
    else if (k === "token") s.token = t.value.trim();
    else if (k === "fine") s.fine = Math.max(0, +t.value || 0);
    else if (k === "hits") s.hits = Math.min(10, Math.max(1, +t.value || 2));
    else if (k === "review") s.review = t.checked;
    save();
  });

  syncFees();
  if (c().running && c().mode === "demo") startDemo();
  draw();
})();
