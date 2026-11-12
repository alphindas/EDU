# EduNest

4-role school portal (Admin · Teacher · Student · Parent) per [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md).

| Part | Stack | Port |
|---|---|---|
| `backend/` | FastAPI · SQLAlchemy · SQLite (Postgres-ready) · JWT · RBAC · multi-tenant | 8000 |
| `frontend/` | React · Vite · TypeScript · Tailwind · shadcn-style UI · i18next (en/te/hi) · TanStack Query · Recharts | 5173 |
| `services/vision/` | Flask smart-attendance + ID-scan microservice (unchanged) | 5000 |

**Status:** Phases 1–2 done. Phase 1: schema, seed, 4-role login, RBAC, CRUD. Phase 2: attendance (manual + face bridge), timetable, homework, leave workflow, ID card QR, in-app notifications.
Phase 3 (quizzes, exams, report card) is next.

## Run on WSL (no Docker) — 3 terminals

One-time setup:
```bash
cd ~/projects/edunest/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed            # creates edunest.db + demo data (add --reset to rebuild)
cd ../frontend && npm install
cd ../services/vision && pip install -r backend/requirements-demo.txt   # use a venv if you prefer
```

Every time:
```bash
# terminal 1 – API  (docs at http://localhost:8000/docs)
cd ~/projects/edunest/backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# terminal 2 – web app  → http://localhost:5173   (proxies /api → :8000, /vision → :5000)
cd ~/projects/edunest/frontend && npm run dev

# terminal 3 – vision service (only needed for face-mode attendance; needs: pip install -r requirements-demo.txt)
cd ~/projects/edunest/services/vision/backend && DEMO_MODE=1 python app.py
```
Open http://localhost:5173 from Windows; WSL2 forwards localhost automatically.

## Run with Docker
```bash
docker compose up --build        # app :5173 · API :8000 · vision :5000
```
Needs Docker Desktop with WSL integration enabled (Settings → Resources → WSL integration).
Set `EDUNEST_SECRET_KEY` in your shell for anything beyond a demo.

## Demo logins (school code `EDN01`)
| Role | Login | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Teacher | `T-001` (also T-002, T-003) | `teacher123` |
| Student | `EN-26-001` … `EN-26-009` | DOB as `DDMMYYYY` (e.g. `15082010`); **forced change on first login** |
| Parent | mobile `9000000001` (2 children) · `9000000002`…`08` | OTP **`000000`** (dev stub, also printed in the API console) |
| Platform admin | `super` (no school code, API only) | `super12345` |

## Tests & build
```bash
cd backend  && .venv/bin/python -m pytest -q      # 31 tests incl. cross-school isolation
cd frontend && npm run build                      # type-check + production build
```

## Architecture notes
- **Multi-tenant:** every school-owned table has `school_id`. Routes filter explicitly, *and* a session-level ORM hook
  (`app/db.py`) appends `school_id = <caller's school>` to every SELECT/UPDATE/DELETE, so a forgotten filter cannot leak.
  `tests/test_tenant_isolation.py` seeds two schools with identical logins and proves A can never read/modify B.
- **Auth:** bcrypt passwords; access (15 min) + refresh (7 d) JWT; students start with a DOB password and are blocked
  from everything except `/auth/me` and `/auth/change-password` until they change it; parents use mobile + OTP
  (`app/otp.py` – swap `DevOtpProvider` for an SMS gateway); login/OTP endpoints are rate-limited.
- **RBAC:** `require_roles(...)` per route plus row-level checks (teacher → own sections, student → self, parent → own children).
- **Vision bridge:** `app/vision.py` calls `EDUNEST_VISION_URL` (`/api/start|status|stop|records`, optional `EDUNEST_VISION_TOKEN` sent as `X-Token`). Camera rows are re-mapped to the caller's section roster by admission no. and returned as a *proposal*; nothing is saved until the teacher confirms. The vision service is single-session/single-tenant, so the bridge allows one session at a time and only the school that started it can read or stop it.
- **Uploads:** `EDUNEST_UPLOAD_DIR` (default `./uploads`, `/data/uploads` in Docker), `<school_id>/<category>/<uuid>.<ext>`, type sniffed from bytes (png/jpg/webp/pdf/ogg/webm/mp3/wav/m4a only), `EDUNEST_MAX_UPLOAD_MB` (8), served only through authenticated routes.
- **Migrations:** tables are created with `create_all` for now; add Alembic before moving to Postgres.

## Known gaps
Phase 2: leave quotas/admin-defined leave types (fixed set: sick/casual/family/other), parent SMS/WhatsApp/push (in-app only), substitutions/swap requests, timetable auto-generate, gate-scan log, in-browser voice recorder (voice notes upload as files), camera QR scanning in the browser (use a USB scanner or paste), Alembic.

Phase 1:
Admin 2FA, bulk Excel import, student/teacher *edit* forms in the UI (API supports PATCH), audit log table, PWA/offline.
