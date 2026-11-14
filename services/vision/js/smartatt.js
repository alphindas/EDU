// EduNest – SMART ATTENDANCE (Cerebromark integration)
// Two engines, one UI:
//   • Demo simulation  – runs entirely in the browser (optionally with your webcam preview).
//   • Cerebromark server – real AI face recognition (InsightFace) over a Hikvision/RTSP/USB camera.
//     The browser polls /api/status, shows the MJPEG /video_feed, and imports results into the register.
(() => {
  "use strict";

  // ---------------------------------------------------------------- icons / nav
  Object.assign(P, {
    scan: "M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3M9 10v1.5M15 10v1.5M9.5 15c1.4 1.1 3.6 1.1 5 0",
    cam: "M3 7h4l2-3h6l2 3h4v13H3zM12 17a4 4 0 100-8 4 4 0 000 8z",
    dl: "M12 3v12M7 10l5 5 5-5M4 21h16",
    clock: "M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v5l3 2",
    check: "M5 13l4 4L19 7",
    plug: "M9 2v6M15 2v6M7 8h10v4a5 5 0 01-10 0zM12 17v5",
  });
  const at = NAV.findIndex(n => n[0] === "att");
  NAV.splice(at + 1, 0, ["smart", "Smart Attendance", "scan"]);

  // ---------------------------------------------------------------- state
  const DEF = {
    mode: "demo", url: (location.protocol==="http:"&&location.hostname?"http://"+location.hostname:"http://localhost")+":5000", period: 1, running: false, t0: 0, sid: null,
    marks: {}, log: [], lateMin: 10, tab: "live", online: null, camOn: false, sessions: [],
    periods: { 1: ["08:45", "09:40"], 2: ["09:41", "10:30"], 3: ["10:50", "11:40"], 4: ["11:41", "12:30"], 5: ["13:30", "14:20"] },
  };
  S.sa = Object.assign({}, DEF, S.sa || {});
  S.sa.camOn = false; // a page reload always drops the camera stream
  const sa = () => S.sa;
  const isLive = () => sa().mode === "live";
  const base = () => sa().url.replace(/\/+$/, "");
  const fmt = ms => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const mmss = ms => { const s = Math.max(0, Math.floor(ms / 1000)); return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); };
  const LBL = { P: "Present", L: "Late", A: "Absent" };

  function counts() {
    let p = 0, l = 0, a = 0, cs = [];
    ST.forEach(x => {
      const m = sa().marks[x.id];
      if (!m) return;
      if (m.st === "P") p++; else if (m.st === "L") l++; else a++;
      if (m.c) cs.push(m.c);
    });
    return { p, l, a, w: ST.length - p - l - a, conf: cs.length ? Math.round(cs.reduce((x, y) => x + y, 0) / cs.length * 100) : null };
  }
  function curPeriod() {
    const now = new Date(), cur = now.getHours() * 60 + now.getMinutes();
    for (const k in sa().periods) {
      const [a, b] = sa().periods[k].map(t => { const [h, m] = t.split(":"); return +h * 60 + +m; });
      if (cur >= a && cur <= b) return +k;
    }
    return null;
  }

  // ---------------------------------------------------------------- recognition events
  const flash = [];
  function mark(id, conf, st, src, time) {
    const s = sa();
    if (s.marks[id]) return false;
    const stu = ST.find(x => x.id === id);
    if (!stu) return false;
    s.marks[id] = { t: time || Date.now(), c: conf, st, src };
    s.log.unshift({ t: time || Date.now(), id, n: stu.n, c: conf, st });
    s.log.length = Math.min(s.log.length, 40);
    flash.push({ n: stu.n.split(" ")[0], t: Date.now(), x: .1 + ((hs(id) * 7) % 62) / 100, y: .16 + ((hs(id) * 3) % 38) / 100, c: conf });
    return true;
  }
  function resetSession() { const s = sa(); s.marks = {}; s.log = []; flash.length = 0; }

  // ---------------------------------------------------------------- persistent stage (survives full redraws)
  const stage = document.createElement("div");
  stage.className = "sa-stage";
  stage.innerHTML = `<video muted playsinline></video><img alt="Live camera feed"><canvas width="1280" height="720"></canvas>
    <div class="sa-idle"><div class="big"><svg class="ic" viewBox="0 0 24 24"><path d="${P.scan}"/></svg></div><b>Camera idle</b><span class="sm">Start a session to begin recognising faces</span></div>
    <div class="sa-hud"><i class="c tl"></i><i class="c tr"></i><i class="c bl"></i><i class="c br"></i><span class="scanline"></span><span class="sa-rec">SCANNING</span><span class="sa-src"></span></div>`;
  const vid = stage.querySelector("video"), img = stage.querySelector("img"), cv = stage.querySelector("canvas"), g = cv.getContext("2d");
  img.addEventListener("error", () => { img.style.display = "none"; });
  let accent = "#3b82f6", accent2 = "#7c5cff", boxes = [], det = null, detT = null;

  function attach() {
    const slot = document.getElementById("sa-slot");
    if (slot && stage.parentNode !== slot) { slot.appendChild(stage); }
    if (slot) {
      const cs = getComputedStyle(document.documentElement);
      accent = cs.getPropertyValue("--ac").trim() || accent; accent2 = cs.getPropertyValue("--ac2").trim() || accent2;
      syncStage();
      if (vid.srcObject && vid.paused) vid.play().catch(() => {});
    }
  }
  window.__afterDraw.push(attach);

  function syncStage() {
    const s = sa(), on = s.running, live = isLive();
    stage.classList.toggle("on", on);
    stage.querySelector(".sa-idle").style.display = on ? "none" : "flex";
    stage.querySelector(".sa-src").textContent = live ? "Cerebromark · " + base().replace(/^https?:\/\//, "") : "Demo · " + (s.camOn ? "webcam" : "simulated feed");
    vid.style.display = !live && s.camOn ? "block" : "none";
    if (live && on && s.online) {
      const u = base() + "/video_feed";
      if (img.dataset.u !== u) { img.dataset.u = u; img.src = u + "?t=" + Date.now(); }
      img.style.display = "block";
    } else { img.removeAttribute("src"); img.dataset.u = ""; img.style.display = "none"; }
  }

  // ---------------------------------------------------------------- canvas overlay (boxes + recognition labels)
  function roundBox(x, y, w, h, col) {
    g.strokeStyle = col; g.lineWidth = 4; const L = 26;
    [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]].forEach(([cx, cy, dx, dy]) => {
      g.beginPath(); g.moveTo(cx, cy + dy * L); g.lineTo(cx, cy); g.lineTo(cx + dx * L, cy); g.stroke();
    });
  }
  function label(text, x, y, col) {
    g.font = "600 24px Inter, system-ui, sans-serif";
    const w = g.measureText(text).width + 24;
    g.fillStyle = col; g.beginPath(); g.roundRect ? g.roundRect(x, y - 38, w, 34, 17) : g.rect(x, y - 38, w, 34); g.fill();
    g.fillStyle = "#fff"; g.fillText(text, x + 12, y - 14);
  }
  let dirty = false;
  function render() {
    requestAnimationFrame(render);
    const W = cv.width, H = cv.height, now = Date.now();
    if (!stage.isConnected || !sa().running || isLive()) { if (dirty) { g.clearRect(0, 0, W, H); dirty = false; } return; }
    dirty = true;
    g.clearRect(0, 0, W, H);
    const s = sa(), recent = flash.filter(f => now - f.t < 2800);
    if (s.camOn && vid.videoWidth) {
      const k = W / vid.videoWidth;
      boxes.forEach((b, i) => {
        const f = recent[recent.length - 1 - i];
        roundBox(b.x * k, b.y * k, b.width * k, b.height * k, f ? "#3ee8a5" : "#ffffffcc");
        label(f ? f.n + "  " + Math.round(f.c * 100) + "%" : "Scanning…", b.x * k, b.y * k, f ? "#17a673" : "#0b1a3caa");
      });
    } else {
      // simulated classroom feed: soft grid + a box for every fresh recognition
      g.strokeStyle = "#ffffff0d"; g.lineWidth = 1;
      for (let x = 0; x < W; x += 64) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); }
      for (let y = 0; y < H; y += 64) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
      recent.forEach(f => {
        const a = 1 - (now - f.t) / 2800, x = f.x * W, y = f.y * H;
        g.globalAlpha = Math.min(1, a * 1.6);
        g.fillStyle = "#3ee8a51a"; g.fillRect(x, y, 170, 210);
        roundBox(x, y, 170, 210, "#3ee8a5");
        g.fillStyle = "#3ee8a566"; g.beginPath(); g.arc(x + 85, y + 82, 36, 0, 7); g.fill(); g.fillRect(x + 35, y + 130, 100, 60);
        label(f.n + "  " + Math.round(f.c * 100) + "%", x, y, "#17a673");
        g.globalAlpha = 1;
      });
    }
  }
  requestAnimationFrame(render);

  // ---------------------------------------------------------------- webcam (demo mode)
  async function camToggle() {
    const s = sa();
    if (s.camOn) { stopCam(); syncStage(); draw(); return; }
    if (!navigator.mediaDevices?.getUserMedia) return toast("Camera needs https:// or localhost");
    try {
      vid.srcObject = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: 1280, height: 720 }, audio: false });
      await vid.play(); s.camOn = true;
      if ("FaceDetector" in window) {
        det = det || new FaceDetector({ fastMode: true, maxDetectedFaces: 12 });
        detT = setInterval(async () => { if (vid.readyState < 2) return; try { boxes = (await det.detect(vid)).map(f => f.boundingBox); } catch (e) { boxes = []; } }, 350);
      } else toast("Webcam on. Face boxes need Chrome's FaceDetector; recognition is simulated.");
    } catch (e) { toast("Camera unavailable: " + (e.message || e.name)); }
    syncStage(); draw();
  }
  function stopCam() {
    clearInterval(detT); boxes = [];
    (vid.srcObject?.getTracks() || []).forEach(t => t.stop()); vid.srcObject = null; sa().camOn = false;
  }

  // ---------------------------------------------------------------- engines
  let demoT = null;
  function startEngine() {
    clearInterval(demoT);
    demoT = setInterval(() => {
      const s = sa(); if (!s.running || isLive()) return;
      const pend = ST.filter(x => !s.marks[x.id] && hs(x.id) % 6 !== 0); // a few students never turn up
      if (pend.length && Math.random() < .6) {
        const x = pend[Math.floor(Math.random() * pend.length)];
        mark(x.id, .62 + Math.random() * .35, hs(x.id) % 5 === 1 ? "L" : "P", "demo");
        paint();
      }
    }, 1100);
  }
  const stopEngine = () => clearInterval(demoT);

  const post = (path, body) => fetch(base() + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });

  async function poll() {
    const s = sa();
    if (!isLive() || !isT()) return;
    if (S.view !== "smart" && !s.running) return;
    try {
      const d = await (await fetch(base() + "/api/status", { cache: "no-store" })).json();
      const wasOnline = s.online; s.online = true;
      if (d.running) {
        if (d.session_id !== s.sid) { resetSession(); s.sid = d.session_id; s.t0 = (d.started_at || Date.now() / 1000) * 1000; s.period = d.period || s.period; }
        s.running = true;
      } else if (s.running) { s.running = false; recordSession(); toast("Server finished the session"); }
      (d.present || []).forEach(p => mark(p["Register Number"], p.Confidence ?? .9, p.Status === "Late" ? "L" : "P", "cam", p.TimeEpoch ? p.TimeEpoch * 1000 : Date.now()));
      if (!wasOnline) draw(); else { syncStage(); paint(); }
    } catch (e) {
      if (s.online !== false) { s.online = false; syncStage(); draw(); } else paint();
    }
  }
  setInterval(poll, 2000);

  // ---------------------------------------------------------------- session bookkeeping
  function recordSession() {
    const s = sa(); if (!Object.keys(s.marks).length) return;
    const res = {}; ST.forEach(x => res[x.id] = s.marks[x.id]?.st || "A");
    s.sessions.unshift({ id: Date.now(), date: iso(0), period: s.period, mode: s.mode, t0: s.t0, t1: Date.now(), res, applied: false });
    s.sessions.length = Math.min(s.sessions.length, 30);
  }

  // ---------------------------------------------------------------- views
  const stateHTML = () => {
    const s = sa(), live = isLive();
    return `<span class="sa-pill ${s.running ? "on" : ""}"><i class="sa-dot"></i>${s.running ? `Scanning · Period ${s.period} · <span id="sa-time">${mmss(Date.now() - s.t0)}</span>` : "Idle"}</span>` +
      (live ? `<span class="sa-pill ${s.online ? "on" : s.online === false ? "err" : ""}"><i class="sa-dot"></i>${s.online ? "Server online" : s.online === false ? "Server unreachable" : "Connecting…"}</span>` : `<span class="sa-pill"><i class="sa-dot"></i>Demo engine</span>`);
  };
  const statsHTML = () => {
    const c = counts(), box = (cls, ic2, v, l) => `<div class="card sa-stat ${cls}"><div class="ico">${ic(ic2)}</div><div><div class="stat gh">${v}</div><div class="mute sm">${l}</div></div></div>`;
    return box("p", "check", c.p, "Present") + box("l", "clock", c.l, "Late") + box("w", "users", c.w + (c.a ? c.a : 0), c.a ? "Waiting / absent" : "Not seen yet") + box("", "spark", c.conf == null ? "—" : c.conf + "%", "Avg match confidence");
  };
  const rosterHTML = () => ST.map(x => {
    const m = sa().marks[x.id], cls = m ? ({ P: "ok", L: "warn", A: "bad" })[m.st] : "wait", fresh = m && Date.now() - m.t < 2500 && !m.manual;
    return `<div class="sa-row ${cls} ${fresh ? "fresh" : ""}"><div class="sa-av">${face(x, 42)}${m && m.st !== "A" ? '<i class="sa-ck"></i>' : ""}</div>
      <div class="sa-who"><b>${esc(x.n)}</b><span class="mute sm">${x.id}${m ? (m.manual ? " · manual" : " · " + fmt(m.t)) : ""}</span></div>
      ${m && m.c ? `<div class="sa-conf" title="Match confidence"><i style="width:${Math.round(m.c * 100)}%"></i><span>${Math.round(m.c * 100)}%</span></div>` : ""}
      <button class="sa-chip ${cls}" data-a="saov" data-i="${x.id}" title="Click to override">${m ? LBL[m.st] : "Waiting"}</button></div>`;
  }).join("");
  const logHTML = () => sa().log.map(e => `<div class="sa-ev"><time>${fmt(e.t)}</time><span><b>${esc(e.n)}</b> recognised · ${Math.round(e.c * 100)}% · <span class="tag ${e.st === "L" ? "warn" : "ok"}">${LBL[e.st]}</span></span></div>`).join("") || '<span class="mute sm">Recognition events will appear here in real time.</span>';

  function paint() {
    const set = (id, h) => { const e = document.getElementById(id); if (e) e.innerHTML = h; };
    set("sa-stats", statsHTML()); set("sa-roster", rosterHTML()); set("sa-log", logHTML()); set("sa-state", stateHTML());
  }
  setInterval(() => { const e = document.getElementById("sa-time"); if (e && sa().running) e.textContent = mmss(Date.now() - sa().t0); }, 1000);
  setInterval(() => { if (sa().running && document.getElementById("sa-roster")) paint(); }, 2600); // clears the "fresh" highlight

  V.smart = () => isT() ? smartT() : smartS();

  function smartT() {
    const s = sa(), tab = s.tab, cp = curPeriod();
    const tabs = [["live", "Live scan"], ["hist", "History"], ["setup", "Setup & server"]].map(t => `<button class="pill ${tab === t[0] ? "on" : ""}" data-a="satab" data-i="${t[0]}">${t[1]}</button>`).join("");
    return `<div class="hero sa-hero"><div><span class="eyebrow">Powered by Cerebromark</span><h1>Smart Attendance</h1><p>AI face recognition marks the class the moment students walk in. No roll call, no proxies.</p></div><div class="sa-state" id="sa-state">${stateHTML()}</div></div>
    <div class="tabs">${tabs}</div>` + (tab === "live" ? liveTab(cp) : tab === "hist" ? histTab() : setupTab());
  }

  function liveTab(cp) {
    const s = sa(), c = counts(), any = Object.keys(s.marks).length > 0, live = isLive();
    return `<div class="grid sa-stats" id="sa-stats">${statsHTML()}</div>
    <div class="sa-layout"><div>
      <div class="card"><div class="row sp"><div class="seg">${[["demo", "Demo simulation"], ["live", "Cerebromark server"]].map(m => `<button class="${s.mode === m[0] ? "on" : ""}" data-a="samode" data-i="${m[0]}">${m[1]}</button>`).join("")}</div>
        <div class="row">${Object.keys(s.periods).map(k => `<button class="pill ${s.period == k ? "on" : ""}" data-a="saper" data-i="${k}" title="${s.periods[k].join(" – ")}">P${k}</button>`).join("")}</div></div>
        <div id="sa-slot"></div>
        <div class="sa-btns">${s.running ? '<button class="btn bad" data-a="sastop">Stop session</button>' : `<button class="btn" data-a="sastart">${ic("scan").replace('class="ic"', 'class="ic" style="vertical-align:-4px;margin-right:6px"')}Start scanning</button>`}
          ${live ? "" : `<button class="btn alt" data-a="sacam">${s.camOn ? "Turn camera off" : "Use my webcam"}</button>`}
          <span class="mute sm" style="flex:1;min-width:180px">${cp ? "Timetable says Period " + cp + " is in session." : "No period in session right now."} ${live ? "Late after " + s.lateMin + " min (server setting)." : ""}</span></div>
        ${live && s.online === false ? `<p class="sm" style="color:var(--bad);margin:10px 0 0">Can't reach ${esc(s.url)}. Start the backend (see <b>Setup &amp; server</b>) or switch to Demo.</p>` : ""}
        ${!live ? '<p class="sm mute" style="margin:10px 0 0">Demo mode simulates recognition in your browser. Switch to <b>Cerebromark server</b> for real face matching.</p>' : ""}</div>
      <div class="card"><h2>Live activity</h2><div class="sa-log" id="sa-log">${logHTML()}</div></div>
    </div>
    <div class="card"><div class="row sp"><h2>Class roster · 10-A</h2><span class="tag">${ST.length} enrolled</span></div><div class="sa-roster" id="sa-roster">${rosterHTML()}</div>
      <p class="sm mute" style="margin:10px 0">Tap a status to override it manually (Present → Late → Absent → clear).</p>
      <div class="row"><button class="btn" data-a="saapply" ${any ? "" : "disabled"}>Apply to attendance register</button><button class="btn alt" data-a="saexport" ${any ? "" : "disabled"}>${ic("dl").replace('class="ic"', 'class="ic" style="vertical-align:-4px;margin-right:6px"')}Export CSV</button><button class="btn alt s" data-a="saclear" ${any && !s.running ? "" : "disabled"}>Clear</button></div></div></div>`;
  }

  function histTab() {
    const s = sa();
    return `<div class="card"><h2>Past scan sessions</h2>${s.sessions.map(x => {
      const v = Object.values(x.res), p = v.filter(k => k === "P").length, l = v.filter(k => k === "L").length, a = v.length - p - l, ab = ST.filter(t => x.res[t.id] === "A");
      return `<div class="stu" style="align-items:flex-start"><div style="flex:1;min-width:200px"><b>${x.date} · Period ${x.period}</b> <span class="tag">${x.mode === "live" ? "Cerebromark" : "Demo"}</span> ${x.applied ? '<span class="tag ok">Applied</span>' : '<span class="tag warn">Not applied</span>'}
        <div class="mute sm">${fmt(x.t0)} – ${fmt(x.t1)} · ${ab.length ? "Absent: " + ab.map(t => esc(t.n.split(" ")[0])).join(", ") : "Everyone present"}</div></div>
        <div class="row"><span class="tag ok">${p} present</span><span class="tag warn">${l} late</span><span class="tag bad">${a} absent</span></div></div>`;
    }).join("") || '<span class="mute">No sessions yet. Run a scan and press Stop to save it here.</span>'}</div>`;
  }

  function setupTab() {
    const s = sa();
    return `<div class="card"><h2>How it works</h2><div class="sa-flow"><div><b>1 · Enrol</b>8–10 photos per student → face embeddings</div><span>›</span><div><b>2 · Capture</b>Camera streams frames to the server</div><span>›</span><div><b>3 · Recognise</b>InsightFace matches each face</div><span>›</span><div><b>4 · Mark</b>Present / Late saved with confidence</div><span>›</span><div><b>5 · Sync</b>Apply to the EduNest register, notify parents</div></div></div>
    <div class="card"><h2>Cerebromark server</h2><div class="row"><input class="in" id="sa-url" style="flex:1;min-width:220px" value="${esc(s.url)}" placeholder="http://localhost:5000" data-sa="url"><button class="btn alt" data-a="satest">${ic("plug").replace('class="ic"', 'class="ic" style="vertical-align:-4px;margin-right:6px"')}Test connection</button></div>
      <p class="sm mute">Page served over https cannot call an http server (browser rule). Open EduNest from <b>http://localhost</b> or put the backend behind https.</p>
      <h2 style="margin-top:14px">Start the backend</h2>
      <div class="code">cd backend
pip install -r requirements.txt

# try it with no camera and no model:
DEMO_MODE=1 python app.py

# real recognition (after building the face DB):
python db_make.py
CAMERA_MODE=hikvision CAMERA_IP=192.168.1.64 CAMERA_PASSWORD=*** python app.py
# or a USB webcam / RTSP stream:
CAMERA_MODE=webcam CAMERA_URL=0 python app.py</div></div>
    <div class="card"><h2>Enrol students</h2><ol class="steps"><li><div>Create <code>NDB/</code> next to <code>db_make.py</code>, one folder per student named <b>&lt;EduNest ID&gt;_&lt;Name&gt;</b>, for example <code>${ST[0].id}_${ST[0].n}</code>. The ID must match the register number so results land on the right student.</div></li><li><div>Add 8–10 clear photos per student (different angles, normal classroom distance).</div></li><li><div>Run <code>python db_make.py</code>. It writes <code>New_face_db/</code>. Restart the server after adding students.</div></li></ol></div>
    <div class="card"><h2>Timetable &amp; rules</h2><p class="sm mute">Used for the "period in session" hint and the History labels. For automatic start/stop on the server run it with <code>SCHEDULER=1</code> and edit <code>TIMETABLE</code> in <code>backend/app.py</code>.</p>
      ${Object.keys(s.periods).map(k => `<div class="sa-tt"><b>Period ${k}</b><input class="in" type="time" value="${s.periods[k][0]}" data-sap="${k}|0"><input class="in" type="time" value="${s.periods[k][1]}" data-sap="${k}|1"></div>`).join("")}
      <div class="row"><label class="sm">Mark late after</label><input class="in" type="number" min="1" max="60" style="width:90px" value="${s.lateMin}" data-sa="lateMin"><span class="sm mute">minutes (demo hint; real value is <code>LATE_AFTER_MIN</code> on the server)</span></div></div>`;
  }

  function smartS() {
    const mine = sa().sessions.filter(x => x.res && x.res[me.id]), today = S.att[me.id];
    return head("Smart Attendance", "Your face-verified check-ins") +
      `<div class="card sa-banner"><div class="t"><div class="ico">${ic("scan")}</div><div><h2 style="margin:0">Walk in, you're marked</h2><div class="mute sm">A classroom camera recognises you automatically. Nothing to tap, nothing to remember.</div></div></div>${today ? `<span class="tag ${today === "P" ? "ok" : today === "L" ? "warn" : "bad"}">Today: ${LBL[today] || "Leave"}</span>` : '<span class="tag">Today: not recorded yet</span>'}</div>
      <div class="card"><h2>Recent scans</h2>${mine.slice(0, 12).map(x => `<div class="stu"><div style="flex:1"><b>${x.date} · Period ${x.period}</b><div class="mute sm">${fmt(x.t0)} – ${fmt(x.t1)}</div></div><span class="tag ${x.res[me.id] === "P" ? "ok" : x.res[me.id] === "L" ? "warn" : "bad"}">${LBL[x.res[me.id]]}</span></div>`).join("") || '<span class="mute">No face-scan sessions recorded yet.</span>'}</div>
      <p class="sm mute">Only the school's own camera and enrolled photos are used. Face data is never shown to other students.</p>`;
  }

  // banner on the manual attendance page (teacher/admin)
  const baseAtt = V.att;
  V.att = () => {
    const h = baseAtt();
    if (!isT()) return h;
    return h.replace("</div>", `</div><div class="card sa-banner"><div class="t"><div class="ico">${ic("scan")}</div><div><h2 style="margin:0">Skip the roll call</h2><div class="mute sm">Let Cerebromark recognise students by face and fill this register for you.</div></div></div><button class="btn" data-a="go" data-i="smart">Open Smart Attendance</button></div>`);
  };

  // ---------------------------------------------------------------- actions
  Object.assign(A, {
    satab: i => { sa().tab = i; },
    samode: i => { const s = sa(); if (s.running) return toast("Stop the session first"); s.mode = i; s.online = null; syncStage(); if (i === "live") poll(); },
    saper: i => { if (sa().running) return toast("Stop the session first"); sa().period = +i; },
    sacam: () => { camToggle(); },
    sastart: async () => {
      const s = sa();
      if (isLive()) {
        try { const r = await post("/api/start", { period: s.period }); s.online = true; s.sid = r.session_id; }
        catch (e) { s.online = false; draw(); return toast("Cannot reach the Cerebromark server"); }
      }
      resetSession(); s.running = true; s.t0 = Date.now();
      if (!isLive()) startEngine();
      syncStage(); toast("Scanning started · Period " + s.period); draw();
    },
    sastop: async () => {
      const s = sa();
      if (isLive()) { try { await post("/api/stop"); } catch (e) { /* server may already be stopped */ } }
      s.running = false; stopEngine(); recordSession(); syncStage(); toast("Session saved to History"); draw();
    },
    saov: id => {
      const s = sa(), m = s.marks[id], next = !m ? "P" : m.st === "P" ? "L" : m.st === "L" ? "A" : null;
      if (next) s.marks[id] = { t: Date.now(), c: null, st: next, manual: true }; else delete s.marks[id];
    },
    saclear: () => { resetSession(); },
    saapply: () => {
      const s = sa();
      ST.forEach(x => { S.att[x.id] = s.marks[x.id]?.st || "A"; });
      S.saved = true;
      const absent = ST.filter(x => S.att[x.id] === "A");
      absent.forEach(x => note(["parent"], x.n + " was marked absent in Period " + s.period + " (face attendance)"));
      const last = s.sessions[0]; if (last && !s.running) last.applied = true;
      toast("Register updated · " + absent.length + " absent, parents notified");
    },
    saexport: () => {
      const s = sa(), rows = [["Register Number", "Name", "Status", "Time", "Confidence", "Source"]];
      ST.forEach(x => { const m = s.marks[x.id]; rows.push([x.id, x.n, m ? LBL[m.st] : "Absent", m && !m.manual ? fmt(m.t) : "", m && m.c ? Math.round(m.c * 100) + "%" : "", m ? (m.manual ? "manual" : m.src) : ""]); });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([rows.map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(",")).join("\n")], { type: "text/csv" }));
      a.download = "smart-attendance-" + iso(0) + "-P" + s.period + ".csv"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    },
    satest: async () => {
      const s = sa(); s.mode = "live"; s.online = null;
      try { const d = await (await fetch(base() + "/api/health", { cache: "no-store" })).json(); s.online = true; toast("Connected" + (d.demo ? " · server is in DEMO mode" : " · camera: " + d.camera_mode)); }
      catch (e) { s.online = false; toast("Could not reach " + s.url); }
    },
  });
  document.addEventListener("change", e => {
    const t = e.target, s = sa();
    if (t.dataset.sa === "url") { s.url = t.value.trim() || DEF.url; s.online = null; save(); }
    if (t.dataset.sa === "lateMin") { s.lateMin = Math.max(1, +t.value || 10); save(); }
    if (t.dataset.sap) { const [p, i] = t.dataset.sap.split("|"); s.periods[p][+i] = t.value; save(); }
  });

  if (sa().running && !isLive()) startEngine();
  draw();
})();
