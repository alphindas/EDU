"""
Smart ID Scan - ID-card compliance engine for EduNest.

This is the "Automated ID Card Enforcement System" merged into the EduNest backend.
It is a Flask blueprint mounted under /api/id by app.py, so ONE server and ONE port
now serve both Smart Attendance (/api/...) and Smart ID Scan (/api/id/...).

How it works
  1. YOLO finds people, a second YOLO model finds ID cards.
  2. A person whose box contains an ID card is "ID verified".
  3. A person with no card gets a face check (InsightFace, the SAME face database that
     Smart Attendance uses - New_face_db - so students are enrolled only once).
  4. A recognised student seen without an ID in ID_CONFIRM_HITS separate frames inside
     ID_CONFIRM_WINDOW seconds becomes ONE violation for that day (snapshot saved).
  5. The violation is "pending" until a teacher/admin confirms or waives it
     (set ID_AUTO_CONFIRM=1 to fine automatically like the original project).
     Confirmed fines are added to the student's EduNest fee dues by the front-end.

Changes compared with the original project (see README for the full list)
  * No more fines on a single frame: needs several sightings (false-positive guard).
  * Human review step before a fine counts (switchable).
  * Uses the shared EduNest face DB instead of students_db.csv / known_embeddings.npy.
  * Fines live in id_data/violations.json (the student CSV is never rewritten).
  * Secrets come from environment variables, never from a committed config file.
  * Optional API token (ID_API_TOKEN) protects snapshots and the violation list.
"""
import csv
import io
import json
import os
import random
import smtplib
import ssl
import threading
import time
import uuid
from datetime import datetime
from email.message import EmailMessage

from flask import Blueprint, Response, abort, jsonify, request, send_from_directory

bp = Blueprint("idscan", __name__, url_prefix="/api/id")
C = {}   # helpers injected by app.py (see register())


def env(key, default):
    return os.environ.get(key, default)


# ============================================================================
# CONFIGURATION (environment variables, see .env.example)
# ============================================================================
PERSON_MODEL = env("ID_MODEL_PERSON", "models/yolov8n.pt")
CARD_MODEL = env("ID_MODEL_CARD", "models/my_model.pt")
PERSON_CONF = float(env("ID_PERSON_CONF", "0.6"))
CARD_CONF = float(env("ID_CARD_CONF", "0.3"))
FACE_THRESHOLD = float(env("ID_FACE_THRESHOLD", "0.5"))
CONFIRM_HITS = int(env("ID_CONFIRM_HITS", "3"))
CONFIRM_WINDOW = float(env("ID_CONFIRM_WINDOW", "20"))
FINE_AMOUNT = float(env("ID_FINE_AMOUNT", "50"))
AUTO_CONFIRM = env("ID_AUTO_CONFIRM", "0") == "1"
DATA_PATH = env("ID_DATA_PATH", "id_data")
CAMERA_MODE = env("ID_CAMERA_MODE", "")          # empty = reuse CAMERA_MODE from app.py
CAMERA_URL = env("ID_CAMERA_URL", "")            # empty = reuse CAMERA_URL from app.py
API_TOKEN = env("ID_API_TOKEN", "")
FRAME_IDLE_SEC = 15                              # browser-webcam session closes after this silence

EMAIL_ENABLED = env("ID_EMAIL_ENABLED", "0") == "1"
SMTP_SERVER = env("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER", "")
SMTP_PASSWORD = env("SMTP_PASSWORD", "")
SMTP_TLS = env("SMTP_TLS", "1") == "1"
EMAIL_SUBJECT = env("ID_EMAIL_SUBJECT", "ID Card Policy Violation - Fine Applied")

SNAP_DIR = os.path.join(DATA_PATH, "snapshots")
VIOL_FILE = os.path.join(DATA_PATH, "violations.json")
CONTACTS_FILE = os.path.join(DATA_PATH, "contacts.csv")     # student_id,email  (optional)
os.makedirs(SNAP_DIR, exist_ok=True)


# ============================================================================
# VIOLATION STORE (thread-safe JSON file)
# ============================================================================
_store_lock = threading.RLock()


def _load():
    with _store_lock:
        if not os.path.exists(VIOL_FILE):
            return []
        try:
            with open(VIOL_FILE, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            print("ID store unreadable, starting empty:", exc)
            return []


def _save(rows):
    with _store_lock:
        tmp = VIOL_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
        os.replace(tmp, VIOL_FILE)          # atomic: a crash never leaves half a file


def today():
    return datetime.now().strftime("%Y-%m-%d")


def create_violation(student_folder, sim, roi=None, source="camera"):
    """One violation per student per day. Returns the record or None if already fined today."""
    reg, name = C["parse_student"](student_folder)
    with _store_lock:
        rows = _load()
        if any(r["student_id"] == reg and r["date"] == today() and r["status"] != "waived" for r in rows):
            return None
        vid = uuid.uuid4().hex[:10]
        snap = ""
        if roi is not None:
            try:
                import cv2
                snap = f"{reg}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                if not cv2.imwrite(os.path.join(SNAP_DIR, snap), roi):
                    snap = ""
            except Exception as exc:
                print("snapshot failed:", exc)
                snap = ""
        rec = {"id": vid, "student_id": reg, "name": name, "ts": time.time(), "date": today(),
               "similarity": round(float(sim), 3), "status": "fined" if AUTO_CONFIRM else "pending",
               "fine": FINE_AMOUNT, "snapshot": snap, "source": source, "note": ""}
        rows.append(rec)
        _save(rows)
    print(f"[ID] violation {vid}: {name} ({reg}) no ID card, match {sim:.2f}, status={rec['status']}")
    if rec["status"] == "fined":
        notify_async(rec)
    return rec


def review_violation(vid, action, note=""):
    with _store_lock:
        rows = _load()
        for r in rows:
            if r["id"] == vid:
                if action == "confirm":
                    r["status"] = "fined"
                elif action == "waive":
                    r["status"] = "waived"
                else:
                    return None
                r["note"] = note[:200]
                r["reviewed_at"] = time.time()
                _save(rows)
                if action == "confirm":
                    notify_async(r)
                return r
    return None


# ============================================================================
# EMAIL (optional) - parent/student contact is kept server-side in contacts.csv
# ============================================================================
def contact_for(student_id):
    if not os.path.exists(CONTACTS_FILE):
        return None
    with open(CONTACTS_FILE, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("student_id") or "").strip() == student_id:
                return (row.get("email") or "").strip() or None
    return None


def total_fined(student_id):
    return sum(r["fine"] for r in _load() if r["student_id"] == student_id and r["status"] == "fined")


def send_email(rec):
    to = contact_for(rec["student_id"])
    if not (EMAIL_ENABLED and to and SMTP_USER and SMTP_PASSWORD):
        return
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = EMAIL_SUBJECT, SMTP_USER, to
    msg.set_content(
        f"Dear {rec['name']},\n\nA fine of Rs. {rec['fine']:.2f} has been applied for not displaying your ID card "
        f"on {datetime.fromtimestamp(rec['ts']).strftime('%Y-%m-%d at %H:%M')}.\n"
        f"Total fines so far: Rs. {total_fined(rec['student_id']):.2f}.\n\n"
        "Please wear your ID card at all times. If you believe this is a mistake, contact the school office.\n\n"
        "Regards,\nEduNest Smart ID Scan\n")
    snap = os.path.join(SNAP_DIR, rec["snapshot"]) if rec.get("snapshot") else None
    if snap and os.path.exists(snap):
        with open(snap, "rb") as fh:
            msg.add_attachment(fh.read(), maintype="image", subtype="jpeg", filename=rec["snapshot"])
    try:
        ctx = ssl.create_default_context()
        if SMTP_TLS:
            srv = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
            srv.starttls(context=ctx)
        else:
            srv = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ctx, timeout=10)
        srv.login(SMTP_USER, SMTP_PASSWORD)
        srv.send_message(msg)
        srv.quit()
        print(f"[ID email] sent to contact of {rec['name']}")
    except Exception as exc:
        print("[ID email] failed:", exc)


def notify_async(rec):
    threading.Thread(target=send_email, args=(rec,), daemon=True).start()


# ============================================================================
# MODELS (lazy: only loaded by real, non-demo sessions)
# ============================================================================
_yolo = {}
_yolo_lock = threading.Lock()


def get_yolo():
    with _yolo_lock:
        if "person" not in _yolo:
            from ultralytics import YOLO
            if not os.path.exists(CARD_MODEL):
                raise RuntimeError(f"ID-card model not found at '{CARD_MODEL}' (ID_MODEL_CARD).")
            print(f"Loading YOLO person model '{PERSON_MODEL}' and ID-card model '{CARD_MODEL}' ...")
            _yolo["person"] = YOLO(PERSON_MODEL)      # downloads yolov8n.pt itself if the file is missing
            _yolo["card"] = YOLO(CARD_MODEL)
    return _yolo["person"], _yolo["card"]


# ============================================================================
# SESSION
# ============================================================================
class IdSession:
    def __init__(self, source):
        self.id = uuid.uuid4().hex[:10]
        self.source = source                   # "server" | "browser"
        self.started = time.time()
        self.ended = None
        self.last_frame = time.time()
        self.stop = threading.Event()
        self.thread = None
        self.frame = None                      # latest annotated JPEG bytes
        self.lock = threading.Lock()
        self.hits = {}                         # student folder -> [timestamps without ID]
        self.stats = {"people": 0, "id_ok": 0, "no_id": 0, "frames": 0}
        self.recent = []                       # last detections for the live log
        self.mat, self.labels = None, []

    def load_faces(self):
        self.mat, self.labels = C["load_face_db"]()

    def log(self, kind, name, sim=None):
        with self.lock:
            self.recent.insert(0, {"t": time.time(), "kind": kind, "name": name,
                                   "sim": None if sim is None else round(float(sim), 3)})
            del self.recent[30:]

    def note_no_id(self, folder, sim, roi):
        """Count a sighting; raise a violation only after CONFIRM_HITS sightings."""
        now = time.time()
        with self.lock:
            seen = [t for t in self.hits.get(folder, []) if now - t <= CONFIRM_WINDOW] + [now]
            self.hits[folder] = seen
            n = len(seen)
        if n >= CONFIRM_HITS:
            rec = create_violation(folder, sim, roi, "camera")
            if rec:
                with self.lock:
                    self.hits[folder] = []
                self.log("violation", rec["name"], sim)
                return n
        self.log("no_id", C["parse_student"](folder)[1], sim)
        return n

    def match(self, embedding):
        import numpy as np
        if self.mat is None or not len(self.labels):
            return None, 0.0
        e = embedding / (np.linalg.norm(embedding) + 1e-6)
        sims = self.mat @ e
        i = int(np.argmax(sims))
        s = float(sims[i])
        return (self.labels[i], s) if s >= FACE_THRESHOLD else (None, s)


SESSION = None
SESSION_LOCK = threading.Lock()


def active():
    """Current session, closing a browser session that stopped sending frames."""
    global SESSION
    s = SESSION
    if s and not s.ended and s.source == "browser" and time.time() - s.last_frame > FRAME_IDLE_SEC:
        s.ended = time.time()
    return s if s and not s.ended else None


def start_session(source):
    global SESSION
    with SESSION_LOCK:
        cur = active()
        if cur:
            return cur
        s = IdSession(source)
        SESSION = s
        if not C["demo"]:
            s.load_faces()
        if source == "server":
            s.thread = threading.Thread(target=worker, args=(s,), daemon=True)
            s.thread.start()
        print(f"--- ID session {s.id} started ({source}) ---")
        return s


def stop_session():
    global SESSION
    with SESSION_LOCK:
        s = active()
        if not s:
            return None
        s.stop.set()
        s.ended = time.time()
    if s.thread:
        s.thread.join(timeout=8)
    print(f"--- ID session {s.id} stopped ---")
    return s


# ============================================================================
# FRAME ANALYSIS
# ============================================================================
GREEN, ORANGE, YELLOW, BLUE = (0, 200, 0), (0, 140, 255), (0, 215, 255), (255, 144, 30)   # BGR


def put_label(img, text, x, y, color):
    import cv2
    (tw, th), bl = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y = y if y - th - 6 > 0 else y + th + 12
    cv2.rectangle(img, (x, y - th - 6), (x + tw + 8, y + bl - 2), color, -1)
    cv2.putText(img, text, (x + 4, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def analyse(frame, sess):
    """Returns (annotated frame, detections). Mirrors the original image_processor.py logic."""
    import cv2
    person_model, card_model = get_yolo()
    face_app = C["get_model"]()
    out = frame.copy()
    H, W = out.shape[:2]
    persons = person_model(frame, classes=[0], conf=PERSON_CONF, verbose=False)[0].boxes
    cards = card_model(frame, conf=CARD_CONF, verbose=False)[0].boxes
    centers = []
    for b in (cards if cards is not None else []):
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        cv2.rectangle(out, (x1, y1), (x2, y2), BLUE, 2)
        centers.append(((x1 + x2) / 2, (y1 + y2) / 2))
    dets = []
    for b in (persons if persons is not None else []):
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
        if y2 - y1 < 30 or x2 - x1 < 20:
            continue
        info = {"status": "unknown", "student_id": None, "name": None, "similarity": None, "bbox": [x1, y1, x2, y2]}
        if any(x1 < cx < x2 and y1 < cy < y2 for cx, cy in centers):
            info["status"], color, text = "id_ok", GREEN, "ID verified"
        else:
            roi = frame[y1:y2, x1:x2]
            color, text, info["status"] = YELLOW, "No ID - unknown", "no_id_unknown"
            try:
                faces = face_app.get(roi)
            except Exception as exc:
                faces = []
                print("face error:", exc)
            if not faces:
                info["status"], text = "no_id_noface", "No ID (face not visible)"
            else:
                f = max(faces, key=lambda z: (z.bbox[2] - z.bbox[0]) * (z.bbox[3] - z.bbox[1]))
                folder, sim = sess.match(f.embedding)
                info["similarity"] = round(sim, 3)
                if folder:
                    reg, name = C["parse_student"](folder)
                    n = sess.note_no_id(folder, sim, roi)
                    info.update(status="no_id_known", student_id=reg, name=name, hits=n)
                    color, text = ORANGE, f"No ID: {name} ({sim:.2f}) {min(n, CONFIRM_HITS)}/{CONFIRM_HITS}"
                else:
                    text = f"No ID - unknown face ({sim:.2f})"
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        put_label(out, text, x1, y1 - 4, color)
        dets.append(info)
    with sess.lock:
        sess.stats["frames"] += 1
        sess.stats["people"] = len(dets)
        sess.stats["id_ok"] = sum(1 for d in dets if d["status"] == "id_ok")
        sess.stats["no_id"] = len(dets) - sess.stats["id_ok"]
    return out, dets


def worker(sess):
    try:
        if C["demo"]:
            return demo_loop(sess)
        source = C["open_source"](CAMERA_MODE or None, CAMERA_URL or None)
        try:
            while not sess.stop.is_set():
                frame = source.read()
                if frame is None:
                    time.sleep(0.5)
                    continue
                out, _ = analyse(frame, sess)
                sess.frame = C["encode_jpeg"](out)
        finally:
            source.close()
    except Exception as exc:
        print("!! ID worker crashed:", exc)
        sess.log("error", str(exc))


def demo_loop(sess):
    """Simulated scene so the whole flow can be tried with no camera and no models."""
    roster = C["roster_ids"]()
    try:
        import cv2
        import numpy as np
        have_cv = True
    except Exception:
        have_cv = False
    boxes = []
    while not sess.stop.is_set():
        # A few students "often forget their card" so the demo reliably shows the full flow
        # (several sightings -> violation -> review -> fine) within about half a minute.
        forgetful = [f for f in roster if sum(map(ord, f)) % 3 == 0] or roster
        folder = random.choice(forgetful if random.random() < 0.6 else roster)
        reg, name = C["parse_student"](folder)
        has_id = random.random() >= (0.8 if folder in forgetful else 0.04)
        sim = random.uniform(0.6, 0.95)
        with sess.lock:
            sess.stats["frames"] += 1
        if has_id:
            sess.log("id_ok", name, sim)
        else:
            sess.note_no_id(folder, sim, None)
        boxes = (boxes + [(name, has_id, time.time())])[-4:]
        with sess.lock:
            live = [b for b in boxes if time.time() - b[2] < 4]
            sess.stats["people"] = len(live)
            sess.stats["id_ok"] = sum(1 for b in live if b[1])
            sess.stats["no_id"] = len(live) - sess.stats["id_ok"]
        if have_cv:
            img = np.zeros((540, 960, 3), dtype="uint8")
            img[:] = (40, 24, 12)
            cv2.putText(img, "SMART ID SCAN - DEMO FEED", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 200, 120), 2)
            for k, (n, ok, _t) in enumerate(live):
                x, y = 80 + k * 210, 150 + (k % 2) * 110
                col = (80, 220, 120) if ok else (40, 140, 255)
                cv2.rectangle(img, (x, y), (x + 170, y + 250), col, 2)
                cv2.putText(img, ("ID ok " if ok else "NO ID ") + n.split()[0], (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
            sess.frame = C["encode_jpeg"](img)
        time.sleep(1.4)


# ============================================================================
# API
# ============================================================================
@bp.before_request
def guard():
    """Optional shared-secret. Preflight requests must pass so the browser can send the header."""
    if request.method == "OPTIONS" or not API_TOKEN:
        return None
    if request.path.endswith("/health"):
        return None
    tok = request.headers.get("X-Token") or request.args.get("token")
    if tok != API_TOKEN:
        return jsonify({"error": "invalid or missing token"}), 401
    return None


@bp.route("/health")
def health():
    ok_models = os.path.exists(CARD_MODEL)
    return jsonify({"ok": True, "demo": C["demo"], "card_model_found": ok_models, "fine": FINE_AMOUNT,
                    "auto_confirm": AUTO_CONFIRM, "confirm_hits": CONFIRM_HITS, "email": EMAIL_ENABLED,
                    "token_required": bool(API_TOKEN)})


@bp.route("/status")
def status():
    s = active()
    rows = _load()
    todays = [r for r in rows if r["date"] == today() and r["status"] != "waived"]
    return jsonify({
        "running": bool(s), "source": s.source if s else None, "session_id": s.id if s else None,
        "started_at": s.started if s else None, "demo": C["demo"],
        "stats": dict(s.stats) if s else {"people": 0, "id_ok": 0, "no_id": 0, "frames": 0},
        "recent": list(s.recent[:20]) if s else [],
        "violations_today": len(todays), "pending": sum(1 for r in rows if r["status"] == "pending"),
        "fine": FINE_AMOUNT, "confirm_hits": CONFIRM_HITS, "auto_confirm": AUTO_CONFIRM,
    })


@bp.route("/start", methods=["POST"])
def api_start():
    body = request.get_json(silent=True) or {}
    source = "browser" if body.get("source") == "browser" else "server"
    try:
        s = start_session(source)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"ok": True, "session_id": s.id, "source": s.source})


@bp.route("/stop", methods=["POST"])
def api_stop():
    s = stop_session()
    return jsonify({"ok": True, "session_id": s.id if s else None})


@bp.route("/frame", methods=["POST"])
def api_frame():
    """Browser-webcam mode: the page posts a JPEG (base64), gets back the annotated frame + detections."""
    if C["demo"]:
        return jsonify({"error": "Server is in DEMO mode - it has no detection models. Use the browser demo or the server camera demo."}), 400
    body = request.get_json(silent=True) or {}
    data = body.get("image") or ""
    if not data:
        return jsonify({"error": "no image"}), 400
    try:
        import base64
        import cv2
        import numpy as np
        raw = base64.b64decode(data.split(",", 1)[-1])
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"error": "could not decode image"}), 400
        s = start_session("browser")
        s.last_frame = time.time()
        out, dets = analyse(frame, s)
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jsonify({"processed_image": base64.b64encode(buf.tobytes()).decode() if ok else None,
                        "detections": dets, "session_id": s.id})
    except Exception as exc:
        print("frame error:", exc)
        return jsonify({"error": str(exc)}), 500


@bp.route("/violations")
def violations():
    rows = _load()
    d, st, sid = request.args.get("date"), request.args.get("status"), request.args.get("student_id")
    if sid:
        rows = [r for r in rows if r["student_id"] == sid]
    if d:
        rows = [r for r in rows if r["date"] == d]
    if st:
        rows = [r for r in rows if r["status"] == st]
    rows.sort(key=lambda r: r["ts"], reverse=True)
    return jsonify({"violations": rows[:500], "fine": FINE_AMOUNT})


@bp.route("/violations/<vid>/review", methods=["POST"])
def review(vid):
    body = request.get_json(silent=True) or {}
    rec = review_violation(vid, body.get("action", ""), str(body.get("note", "")))
    if not rec:
        return jsonify({"error": "unknown violation or action"}), 404
    return jsonify({"ok": True, "violation": rec})


@bp.route("/ledger")
def ledger():
    out = {}
    for r in _load():
        e = out.setdefault(r["student_id"], {"student_id": r["student_id"], "name": r["name"],
                                              "count": 0, "fined": 0.0, "pending": 0})
        if r["status"] == "fined":
            e["count"] += 1
            e["fined"] += r["fine"]
        elif r["status"] == "pending":
            e["pending"] += 1
    return jsonify(sorted(out.values(), key=lambda e: -e["fined"]))


@bp.route("/snapshot/<path:name>")
def snapshot(name):
    if "/" in name or "\\" in name or not name.lower().endswith(".jpg"):
        abort(404)
    return send_from_directory(os.path.abspath(SNAP_DIR), name)


@bp.route("/export")
def export():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Violation ID", "Student ID", "Name", "Date", "Time", "Match", "Status", "Fine", "Note"])
    for r in sorted(_load(), key=lambda r: r["ts"]):
        w.writerow([r["id"], r["student_id"], r["name"], r["date"],
                    datetime.fromtimestamp(r["ts"]).strftime("%H:%M:%S"), r["similarity"], r["status"], r["fine"], r.get("note", "")])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=id-violations-{today()}.csv"})


@bp.route("/video_feed")
def video_feed():
    s = active()
    if not s:
        return "No active ID session", 404

    def gen():
        last = None
        while s and not s.ended:
            fr = s.frame
            if fr is not None and fr is not last:
                last = fr
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + fr + b"\r\n"
            time.sleep(0.08)

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ============================================================================
# REGISTRATION (called from app.py)
# ============================================================================
def register(app, helpers):
    """helpers: get_model, load_face_db, open_source, encode_jpeg, parse_student, roster_ids, demo"""
    C.update(helpers)
    app.register_blueprint(bp)
    print(f"Smart ID Scan ready  |  fine={FINE_AMOUNT:g}  auto_confirm={AUTO_CONFIRM}  "
          f"confirm_hits={CONFIRM_HITS}  token={'on' if API_TOKEN else 'off'}  email={'on' if EMAIL_ENABLED else 'off'}")
