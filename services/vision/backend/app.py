"""
Cerebromark API server – the AI engine behind EduNest "Smart Attendance" AND "Smart ID Scan".
(Smart ID Scan lives in idscan.py and is mounted under /api/id by the registration call near the bottom.)

What changed compared with the original Cerebromark app.py
  * Recognition runs in a background worker thread. (Originally it only ran while
    a browser tab was streaming /video_feed, so no tab = no attendance.)
  * Clean JSON API (/api/...) with CORS so the EduNest frontend can talk to it.
  * Students are marked Present or Late (late after LATE_AFTER_MIN minutes).
  * Works with: Hikvision camera, any RTSP stream, a USB webcam, or DEMO_MODE
    (no camera / no model needed - perfect for trying the integration).
  * CPU fallback when CUDA is not available. Settings come from env variables.
  * Fixed: absent/present CSV path bug, and the 1:30 AM timetable entry (now 13:30).

Quick start (demo, nothing to install except Flask):
    pip install flask
    DEMO_MODE=1 python app.py         (Windows PowerShell:  $env:DEMO_MODE=1; python app.py)
"""
import csv
import json
import os


def _load_dotenv(path=None):
    """Tiny .env reader (no extra dependency) so Windows/macOS/Linux all configure the server the same way.
    Real environment variables always win over the file."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
# Run relative paths (models/, New_face_db/, id_data/ ...) from this folder, wherever the server is started from.
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import random
import threading
import time
import uuid
from datetime import datetime, timedelta

from flask import Flask, Response, jsonify, request

# ============================================================================
# CONFIGURATION  (override with environment variables, see .env.example)
# ============================================================================
def env(key, default):
    return os.environ.get(key, default)

DEMO_MODE = env("DEMO_MODE", "0") == "1"
CAMERA_MODE = env("CAMERA_MODE", "webcam")           # webcam | rtsp | hikvision
CAMERA_IP = env("CAMERA_IP", "192.168.1.64")
USERNAME = env("CAMERA_USER", "admin")
PASSWORD = env("CAMERA_PASSWORD", "change-me")
CHANNEL_ID_STREAM = int(env("CHANNEL_ID_STREAM", "101"))
CHANNEL_ID_PTZ = int(env("CHANNEL_ID_PTZ", "1"))
CAMERA_URL = env("CAMERA_URL", "0")                  # rtsp://... or webcam index

MODEL_NAME = env("MODEL_NAME", "buffalo_l")
RECOGNITION_THRESHOLD = float(env("RECOGNITION_THRESHOLD", "0.5"))
DB_PATH = env("DB_PATH", "New_face_db")
USE_GPU = env("USE_GPU", "0") == "1"

LATE_AFTER_MIN = int(env("LATE_AFTER_MIN", "10"))
ATTENDANCE_PATH = env("ATTENDANCE_PATH", "attendance_files")
RECORDING_PATH = env("RECORDING_PATH", "recordings")
RECORD_VIDEO = env("RECORD_VIDEO", "0") == "1"
SCHEDULER_ENABLED = env("SCHEDULER", "0") == "1"
TIMEZONE = env("TIMEZONE", "Asia/Kolkata")

PTZ_ENABLED = env("PTZ_ENABLED", "0") == "1"
PTZ_ZOOM_SPEED = 1
PTZ_ZOOM_DURATION_SEC = 17
PTZ_PAUSE_DURATION_SEC = 180

# 24-hour clock. (The original had 1:30 which is 1:30 AM - fixed to 13:30.)
TIMETABLE = {
    1: ("08:45", "09:40"),
    2: ("09:41", "10:30"),
    3: ("10:50", "11:40"),
    4: ("11:41", "12:30"),
    5: ("13:30", "14:20"),
}

# Used only when DB_PATH has no students (so demo mode always has a class).
DEMO_ROSTER = [
    "EN-26-001_Aarav Reddy", "EN-26-002_Diya Sharma", "EN-26-003_Kabir Rao",
    "EN-26-004_Meera Nair", "EN-26-005_Rohan Das", "EN-26-006_Sana Khan",
    "EN-26-007_Tara Iyer", "EN-26-008_Vihaan Patel",
]

os.makedirs(ATTENDANCE_PATH, exist_ok=True)
os.makedirs(RECORDING_PATH, exist_ok=True)

app = Flask(__name__)


# ============================================================================
# CORS (no extra dependency needed)
# ============================================================================
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Token"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Private-Network"] = "true"
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ============================================================================
# HELPERS
# ============================================================================
def parse_student(folder):
    """'EN-26-001_Aarav Reddy' -> ('EN-26-001', 'Aarav Reddy')."""
    parts = folder.split("_", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (folder, "Unknown")


def roster_ids():
    """All enrolled students (folder names inside the face DB)."""
    ids = []
    if os.path.isdir(DB_PATH):
        ids = sorted(d for d in os.listdir(DB_PATH) if os.path.isdir(os.path.join(DB_PATH, d)))
    return ids or list(DEMO_ROSTER)


def student_row(folder, status, t=None, conf=None):
    reg, name = parse_student(folder)
    row = {"Register Number": reg, "Name": name, "Status": status}
    if t is not None:
        row["Time"] = datetime.fromtimestamp(t).strftime("%H:%M:%S")
        row["TimeEpoch"] = t
    if conf is not None:
        row["Confidence"] = round(float(conf), 3)
    return row


# ============================================================================
# SESSION STATE
# ============================================================================
class Session:
    def __init__(self, period):
        self.id = uuid.uuid4().hex[:10]
        self.period = period
        self.started = time.time()
        self.ended = None
        self.marks = {}               # folder -> {"t": epoch, "c": confidence, "status": ...}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.frame = None             # latest annotated JPEG bytes

    def mark(self, folder, conf):
        with self.lock:
            if folder in self.marks:
                return False
            late = (time.time() - self.started) / 60.0 > LATE_AFTER_MIN
            self.marks[folder] = {"t": time.time(), "c": conf, "status": "Late" if late else "Present"}
            reg, name = parse_student(folder)
            print(f"[period {self.period}] {name} ({reg}) -> {self.marks[folder]['status']} ({conf:.2f})")
            return True

    def present_rows(self):
        with self.lock:
            items = sorted(self.marks.items(), key=lambda kv: kv[1]["t"])
        return [student_row(f, m["status"], m["t"], m["c"]) for f, m in items]


SESSION = None
SESSION_LOCK = threading.Lock()


# ============================================================================
# FACE MODEL + DATABASE  (lazy: only imported for real, non-demo sessions)
# ============================================================================
_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    with _model_lock:
        if _model is None:
            import insightface
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if USE_GPU else ["CPUExecutionProvider"]
            print(f"Loading InsightFace '{MODEL_NAME}' on {providers[0]} ...")
            _model = insightface.app.FaceAnalysis(name=MODEL_NAME, providers=providers)
            _model.prepare(ctx_id=0 if USE_GPU else -1, det_size=(640, 640))
    return _model


def load_face_db():
    """Returns (matrix[N,512] of unit vectors, labels[N])."""
    import numpy as np
    embs, labels = [], []
    if not os.path.isdir(DB_PATH):
        print(f"ERROR: face database '{DB_PATH}' not found - run db_make.py first.")
        return np.zeros((0, 512), dtype="float32"), []
    for person in os.listdir(DB_PATH):
        folder = os.path.join(DB_PATH, person)
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if fn.endswith(".npy"):
                try:
                    e = np.load(os.path.join(folder, fn)).astype("float32")
                    embs.append(e / (np.linalg.norm(e) + 1e-6))
                    labels.append(person)
                except Exception as exc:
                    print(f"Skipping {fn}: {exc}")
    mat = np.stack(embs) if embs else np.zeros((0, 512), dtype="float32")
    print(f"Face DB loaded: {len(labels)} embeddings, {len(set(labels))} students")
    return mat, labels


def match_face(embedding, mat, labels):
    import numpy as np
    if not labels:
        return "Unknown", 0.0
    e = embedding / (np.linalg.norm(embedding) + 1e-6)
    sims = mat @ e
    i = int(np.argmax(sims))
    s = float(sims[i])
    return (labels[i], s) if s > RECOGNITION_THRESHOLD else ("Unknown", s)


# ============================================================================
# CAMERA SOURCES
# ============================================================================
class HikvisionSource:
    def __init__(self):
        from hikvisionapi import Client
        self.client = Client(f"http://{CAMERA_IP}", USERNAME, PASSWORD, timeout=30)

    def read(self):
        import cv2
        import numpy as np
        r = self.client.Streaming.channels[CHANNEL_ID_STREAM].picture(method="get", type="opaque_data")
        return cv2.imdecode(np.asarray(bytearray(r.content), dtype=np.uint8), cv2.IMREAD_COLOR)

    def close(self):
        pass


class CvSource:
    def __init__(self, url=None):
        import cv2
        url = url or CAMERA_URL
        src = int(url) if url.isdigit() else url
        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video source {url!r}")

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def close(self):
        self.cap.release()


def open_source(mode=None, url=None):
    """mode/url let Smart ID Scan use a different camera than Smart Attendance (ID_CAMERA_MODE / ID_CAMERA_URL)."""
    mode = mode or CAMERA_MODE
    return HikvisionSource() if mode == "hikvision" else CvSource(url)


# ---- optional PTZ patrol (Hikvision) ----------------------------------------
_ptz_active = threading.Event()


def send_ptz_zoom(value):
    import requests
    from requests.auth import HTTPDigestAuth
    url = f"http://{CAMERA_IP}/ISAPI/PTZCtrl/channels/{CHANNEL_ID_PTZ}/continuous"
    body = f'<?xml version="1.0" encoding="UTF-8"?><PTZData><pan>0</pan><tilt>0</tilt><zoom>{value}</zoom></PTZData>'
    try:
        requests.put(url, data=body, headers={"Content-Type": "application/xml"},
                     auth=HTTPDigestAuth(USERNAME, PASSWORD), timeout=3)
    except Exception as exc:
        print("PTZ error:", exc)


def ptz_patrol():
    send_ptz_zoom(PTZ_ZOOM_SPEED); time.sleep(20); send_ptz_zoom(0)
    while _ptz_active.is_set():
        for direction in (-PTZ_ZOOM_SPEED, PTZ_ZOOM_SPEED):
            if not _ptz_active.is_set():
                break
            time.sleep(PTZ_PAUSE_DURATION_SEC)
            send_ptz_zoom(direction); time.sleep(PTZ_ZOOM_DURATION_SEC); send_ptz_zoom(0)
    send_ptz_zoom(0)


# ============================================================================
# RECOGNITION WORKERS
# ============================================================================
def encode_jpeg(frame, width=960):
    import cv2
    h, w = frame.shape[:2]
    if w > width:
        frame = cv2.resize(frame, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes() if ok else None


def demo_loop(sess):
    """Simulated recognition: students 'walk in' one by one. No camera or model."""
    roster = roster_ids()
    never = {f for f in roster if sum(map(ord, f)) % 6 == 0}   # a few stay absent
    try:
        import cv2, numpy as np
        have_cv = True
    except Exception:
        have_cv = False
    recent = []
    while not sess.stop.is_set():
        pending = [f for f in roster if f not in sess.marks and f not in never]
        if pending and random.random() < 0.55:
            f = random.choice(pending)
            if sess.mark(f, random.uniform(0.62, 0.97)):
                recent.append((parse_student(f)[1], time.time()))
        if have_cv:
            img = np.zeros((540, 960, 3), dtype="uint8")
            img[:] = (40, 24, 12)
            cv2.putText(img, "CEREBROMARK - DEMO FEED", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 200, 120), 2)
            for k, (n, t) in enumerate([r for r in recent if time.time() - r[1] < 3][-5:]):
                x, y = 80 + k * 170, 160 + (k % 2) * 120
                cv2.rectangle(img, (x, y), (x + 150, y + 190), (80, 220, 120), 2)
                cv2.putText(img, n.split()[0], (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 220, 120), 2)
            sess.frame = encode_jpeg(img)
        time.sleep(1.0)


def real_loop(sess):
    import cv2
    model = get_model()
    mat, labels = load_face_db()
    source = open_source()
    writer = None
    if RECORD_VIDEO:
        frame = source.read()
        if frame is not None:
            h, w = frame.shape[:2]
            name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + f"_period_{sess.period}.mp4"
            writer = cv2.VideoWriter(os.path.join(RECORDING_PATH, name), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (w, h))
    if PTZ_ENABLED and CAMERA_MODE == "hikvision":
        _ptz_active.set()
        threading.Thread(target=ptz_patrol, daemon=True).start()
    try:
        while not sess.stop.is_set():
            frame = source.read()
            if frame is None:
                time.sleep(0.5)
                continue
            for face in model.get(frame):
                x1, y1, x2, y2 = face.bbox.astype(int)
                folder, sim = match_face(face.embedding, mat, labels)
                known = folder != "Unknown"
                if known:
                    sess.mark(folder, sim)
                label = f"{parse_student(folder)[1]} ({sim:.2f})" if known else f"Unknown ({sim:.2f})"
                color = (80, 220, 120) if known else (60, 60, 230)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, max(20, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            if writer is not None:
                writer.write(frame)
            sess.frame = encode_jpeg(frame)
    finally:
        _ptz_active.clear()
        if writer is not None:
            writer.release()
        source.close()


def worker(sess):
    try:
        (demo_loop if DEMO_MODE else real_loop)(sess)
    except Exception as exc:
        print("!! recognition worker crashed:", exc)


# ============================================================================
# SESSION CONTROL + STORAGE
# ============================================================================
def start_session(period):
    global SESSION
    with SESSION_LOCK:
        if SESSION and not SESSION.ended:
            return SESSION
        SESSION = Session(period)
        SESSION.thread = threading.Thread(target=worker, args=(SESSION,), daemon=True)
        SESSION.thread.start()
        print(f"--- Session {SESSION.id} started for period {period} ---")
        return SESSION


def stop_session():
    global SESSION
    with SESSION_LOCK:
        s = SESSION
        if not s or s.ended:
            return None
        s.stop.set()
        s.ended = time.time()
    if s.thread:
        s.thread.join(timeout=8)
    save_session(s)
    print(f"--- Session {s.id} stopped ---")
    return s


def save_session(s):
    date = datetime.fromtimestamp(s.started).strftime("%Y-%m-%d")
    folder = os.path.join(ATTENDANCE_PATH, f"period_{s.period}")
    os.makedirs(folder, exist_ok=True)
    present = s.present_rows()
    marked = set(s.marks)
    absent = [student_row(f, "Absent") for f in roster_ids() if f not in marked]
    data = {"date": date, "period": s.period, "session_id": s.id,
            "started": s.started, "ended": s.ended, "present": present, "absent": absent}
    with open(os.path.join(folder, f"{date}_period_{s.period}.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    for kind, rows in (("present", present), ("absent", absent)):
        path = os.path.join(folder, f"{date}_period_{s.period}_{kind}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            fields = ["Register Number", "Name", "Status", "Time", "Confidence"]
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)


# ============================================================================
# API
# ============================================================================
@app.route("/")
def index():
    return jsonify({"service": "Cerebromark API for EduNest", "demo": DEMO_MODE,
                    "docs": ["/api/health", "/api/status", "/api/roster", "/api/records", "/video_feed",
                             "/api/id/health", "/api/id/status", "/api/id/violations", "/api/id/video_feed"]})


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "demo": DEMO_MODE, "camera_mode": CAMERA_MODE, "time": time.time()})


@app.route("/api/status")
def status():
    s = SESSION
    running = bool(s and not s.ended)
    return jsonify({
        "running": running,
        "demo": DEMO_MODE,
        "session_id": s.id if s else None,
        "period": s.period if s else 0,
        "started_at": s.started if s else None,
        "late_after_min": LATE_AFTER_MIN,
        "total": len(roster_ids()),
        "present": s.present_rows() if s else [],
    })


@app.route("/api/roster")
def roster():
    return jsonify([student_row(f, "Enrolled") for f in roster_ids()])


@app.route("/api/start", methods=["POST"])
def api_start():
    body = request.get_json(silent=True) or {}
    try:
        period = int(body.get("period", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "period must be a number"}), 400
    s = start_session(period)
    return jsonify({"ok": True, "session_id": s.id, "period": s.period})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    s = stop_session()
    return jsonify({"ok": True, "session_id": s.id if s else None})


@app.route("/api/records")
def records():
    date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    period = request.args.get("period")
    if not period or not period.isdigit():
        return jsonify({"error": "period is required"}), 400
    path = os.path.join(ATTENDANCE_PATH, f"period_{period}", f"{date}_period_{period}.json")
    if not os.path.exists(path):
        return jsonify({"date": date, "period": int(period), "present": [], "absent": []})
    with open(path, encoding="utf-8") as fh:
        return jsonify(json.load(fh))


@app.route("/video_feed")
def video_feed():
    s = SESSION
    if not s or s.ended:
        return "No active session", 404

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
# SMART ID SCAN (ID-card enforcement) - mounted under /api/id, see idscan.py
# ============================================================================
import idscan  # noqa: E402

idscan.register(app, {
    "get_model": get_model, "load_face_db": load_face_db, "open_source": open_source,
    "encode_jpeg": encode_jpeg, "parse_student": parse_student, "roster_ids": roster_ids, "demo": DEMO_MODE,
})


# ============================================================================
# OPTIONAL TIMETABLE SCHEDULER  (SCHEDULER=1)
# ============================================================================
def setup_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    sch = BackgroundScheduler(daemon=True, timezone=TIMEZONE)
    for period, (start, end) in TIMETABLE.items():
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        sch.add_job(start_session, "cron", hour=sh, minute=sm, args=[period], day_of_week="mon-sat")
        sch.add_job(stop_session, "cron", hour=eh, minute=em, day_of_week="mon-sat")
    sch.start()
    print("Scheduler running for periods:", ", ".join(f"{p} {s}-{e}" for p, (s, e) in TIMETABLE.items()))


if __name__ == "__main__":
    print(f"Cerebromark API  |  demo={DEMO_MODE}  camera={CAMERA_MODE}  late_after={LATE_AFTER_MIN}min")
    if SCHEDULER_ENABLED:
        setup_scheduler()
    app.run(host="0.0.0.0", port=int(env("PORT", "5000")), debug=False, threaded=True)
