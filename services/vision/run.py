#!/usr/bin/env python3
"""
EduNest one-command launcher (Windows / macOS / Linux).

    python run.py              # DEMO: whole portal + simulated AI, nothing to set up
    python run.py --real       # REAL: face recognition + ID-card detection on a camera
    python run.py --vendor     # (optional, needs internet once) download pdf.js so PDF-to-quiz works offline

Options:  --port 8000 (portal)   --api-port 5000 (AI server)   --no-browser
Starts two things: the AI server (backend/app.py) and a small web server for the portal, then opens the browser.
Press Ctrl+C to stop both.
"""
import argparse
import http.server
import importlib.util
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")


def have(mod):
    return importlib.util.find_spec(mod) is not None


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def vendor():
    base = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/"
    os.makedirs(os.path.join(ROOT, "vendor"), exist_ok=True)
    for fn in ("pdf.min.js", "pdf.worker.min.js"):
        print("Downloading", fn, "...")
        urllib.request.urlretrieve(base + fn, os.path.join(ROOT, "vendor", fn))
    print("Done. PDF-to-quiz now works without internet.")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser(description="EduNest launcher")
    ap.add_argument("--real", action="store_true", help="real face recognition / ID-card detection (needs backend/requirements.txt)")
    ap.add_argument("--demo", action="store_true", help="simulated AI (default)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--api-port", type=int, default=5000)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--vendor", action="store_true", help="download pdf.js for offline use, then exit")
    a = ap.parse_args()

    if a.vendor:
        return vendor()

    if not have("flask"):
        sys.exit("Flask is missing. Run:\n    pip install -r backend/requirements-demo.txt")
    if a.real:
        missing = [m for m in ("cv2", "numpy", "insightface", "ultralytics", "onnxruntime") if not have(m)]
        if missing:
            sys.exit("Real mode needs: " + ", ".join(missing) + "\nRun:\n    pip install -r backend/requirements.txt")
        if not os.path.isdir(os.path.join(BACKEND, "New_face_db")):
            print("NOTE: no face database yet. Enrol students first (see README step 'Enrol faces'),\n"
                  "      otherwise nobody will be recognised.\n")

    env = dict(os.environ, DEMO_MODE="0" if a.real else "1", PORT=str(a.api_port), PYTHONUNBUFFERED="1")
    api = subprocess.Popen([sys.executable, "app.py"], cwd=BACKEND, env=env)
    time.sleep(1.5)
    if api.poll() is not None:
        sys.exit("The AI server failed to start (see the message above).")

    try:
        web = Server(("0.0.0.0", a.port), Quiet)
    except OSError:
        api.terminate()
        sys.exit(f"Port {a.port} is busy. Try:  python run.py --port {a.port + 1}")
    threading.Thread(target=web.serve_forever, daemon=True).start()

    ip = lan_ip()
    print("\n" + "=" * 62)
    print(" EduNest is running  -  mode:", "REAL AI" if a.real else "DEMO (simulated AI)")
    print(f"   Portal (this computer) : http://localhost:{a.port}")
    print(f"   Portal (same Wi-Fi)    : http://{ip}:{a.port}   (webcam needs localhost or https)")
    print(f"   AI server              : http://localhost:{a.api_port}/api/health")
    print(" Press Ctrl+C to stop.")
    print("=" * 62 + "\n")
    if not a.no_browser:
        webbrowser.open(f"http://localhost:{a.port}")
    try:
        while api.poll() is None:
            time.sleep(0.5)
        print("AI server stopped.")
    except KeyboardInterrupt:
        pass
    finally:
        web.shutdown()
        if api.poll() is None:
            api.terminate()
            try:
                api.wait(5)
            except Exception:
                api.kill()


if __name__ == "__main__":
    main()
