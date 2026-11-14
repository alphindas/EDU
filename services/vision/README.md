# EduNest School Portal – showcase edition

Student / Parent / Teacher / Admin portal with **Smart Attendance** (face recognition) and **Smart ID Scan**
(ID-card enforcement → fines flow into the Fees page).

## 1. Run it (3 commands, Windows / macOS / Linux)

Needs **Python 3.10+** (python.org). Open a terminal in this folder:

    pip install -r backend/requirements-demo.txt
    python run.py

(Windows: if `python` isn't found, use `py run.py`. macOS/Linux: `python3 run.py`.)
Your browser opens at **http://localhost:8000**. Press **Ctrl+C** to stop. That is the full live demo – no camera,
no AI models, no internet needed (all AI is simulated, the workflow is real).

Optional, once, with internet: `python run.py --vendor` → PDF-to-quiz then works offline too.
Optional: open the portal on a projector laptop and from a phone on the same Wi-Fi: use the "same Wi-Fi" URL printed at start.

## 2. Suggested 7-minute live walkthrough
1. **Login screen** → *Teacher*. Home shows today's ID-compliance card.
2. **Smart Attendance** → *Cerebromark server* → Start. Students are "recognised" one by one, late ones flagged → *Stop* → **Apply to attendance register**.
3. **Attendance** page now holds the register. Switch to *Parent* → the absent child's parents are notified (bell icon).
4. **ID Scan** → *Live scan* → Start. After ~30 s students without ID appear under **Violations** as *Pending review*. **Confirm fine** → ₹50 is added on **Fees**; *Waive* takes it back.
5. Log in as *Student* / *Parent* → read-only ID-Scan record, marks, homework, fees, rewards, AI assistant.
6. Teacher → **Quiz**: paste or upload questions, publish; Student → take the quiz.
7. Before the next audience: login screen → **Reset demo data**.

## 3. Real AI mode (live camera, real faces)
    pip install -r backend/requirements.txt          # big download: insightface, onnxruntime, ultralytics
    # Enrol faces (consent required; 8-10 photos each, turn the head slightly between shots):
    cd backend
    python enroll_webcam.py EN-26-001 "Aarav Reddy"   # repeat per person; or put photos in NDB/<ID>_<Name>/ yourself
    python db_make.py                                 # builds New_face_db once (shared by both features)
    cd ..
    python run.py --real

Settings live in `backend/.env` (copy `backend/.env.example`): camera type (`webcam` | `rtsp` | `hikvision`), `CAMERA_URL`,
`ID_FINE_AMOUNT`, `ID_AUTO_CONFIRM`, thresholds, optional e-mail. In the app: **ID Scan → Setup & rules** → *Test connection*.
Attendance and ID Scan both read the camera from the server, so use two cameras (`ID_CAMERA_MODE` / `ID_CAMERA_URL`)
or run one feature at a time; ID Scan also has *Browser webcam* mode (laptop camera, ~1 frame/s).
First real run downloads the InsightFace model (~300 MB) – do this before the demo, with internet.

## 4. What was reviewed / changed in this edition
| Area | Change |
|---|---|
| Launch | New `run.py` – one command starts portal + AI server, works the same on every OS (the old `DEMO_MODE=1 python app.py` syntax fails on Windows) |
| Config | Backend reads `backend/.env`; always runs from its own folder so models/DB paths resolve; default camera is now `webcam` (was `hikvision`, which crashed on laptops) |
| PDF → quiz | Fixed: pdf.js had no worker configured so PDF upload failed; now local-first (`vendor/`) with CDN fallback |
| Demo reliability | Server-side ID-Scan simulation now includes "forgetful" students, so a violation reliably appears in ~30 s (before it almost never did) |
| Portal URL | Backend address defaults to the host the portal was opened from (works from another device, not only `localhost`) |
| UI | Time-based greeting, **Reset demo data** button, favicon |
| Tools | `backend/enroll_webcam.py` – enrol a person from the webcam in ~30 s |

Verified by automated browser tests: all 4 roles and every tab load without errors; ID-Scan demo and server modes
(violation → confirm → fee + notification); Smart Attendance demo and server modes (apply to register); violation
pipeline (3 sightings → snapshot → review → ledger/CSV export) exercised with stand-in detectors.
**Not verifiable without hardware/internet:** real camera accuracy, YOLO/InsightFace model downloads – test these once on the demo laptop.

## 5. Limits to be honest about when presenting
- The portal data (students, homework, marks, fees) is demo data stored in the browser; there is **no real login**. A pilot needs a real database and authentication before any real student data goes in.
- Face matching on children needs written parent/school consent, a privacy policy, and a retention period for `backend/id_data/snapshots`. Keep the teacher-review step on.
- Live classes are simulated (no real video yet).

## API (backend)
Attendance: GET /api/health · /api/status · /api/roster · POST /api/start · /api/stop · GET /api/records · /video_feed
Smart ID Scan under `/api/id`: GET health · status · violations · ledger · export · snapshot/<file> · video_feed;
POST start · stop · frame · violations/<id>/review. Optional `ID_API_TOKEN` shared secret.
