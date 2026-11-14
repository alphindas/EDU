# EduNest: map for future sessions

> **EduNest 2.0 layer (Nov 2026):** `app/models_v2.py` (25 new tables), `providers.py` (OpenAI-compatible/Gemini/stub LLM wrapper), `chitti.py` (shared engine: modes, topic search, solver, English coach, career, parent-leave parser), `kb.py` (offline starter topics), `search.py` (BM25+embedding hybrid + rerank), `brain.py` (signed adaptive puzzles), `gamify.py` (XP/levels/streaks/badges/quests/shop/teams), `seed_v2.py` (illustrative demo data), routers `chitti, game, coach, content, community, transport, insights, ws`. Audit middleware in `main.py`. Frontend: `components/fun/*` (Chitti mascot, art, celebrations, puzzles), new pages under `pages/{student,shared,teacher,parent,admin}`, locales `i18n/locales/{en,te,hi,ml,ta}.json` + `v2/*.json` (deep-merged). Tests: `tests/test_v2.py`; 134 pass. Students need parent AI consent (`EDUNEST_REQUIRE_AI_CONSENT`, off in tests).

4-role school portal (Admin/Teacher/Student/Parent) + AI layer. **Full spec: `docs/BLUEPRINT.md`** (read it before new phases; not repeated here).

## Stack
- `backend/`: FastAPI, SQLAlchemy 2, SQLite (Postgres later), JWT, bcrypt, pytest. Port **8000**.
- `frontend/`: React, Vite, TypeScript, Tailwind 3, shadcn-style UI, i18next (en/te/hi), TanStack Query, Zustand, Recharts. Port **5173** (proxies `/api`→8000, `/vision`→5000).
- `services/vision/`: Flask smart-attendance + ID-scan demo. **Untouched; do not edit.** Port **5000**. Backend calls it over HTTP (`app/vision.py`, face-mode attendance).

## Layout
- `backend/app/`: `models.py` (all tables), `db.py` (engine + tenant guard), `deps.py` (auth/RBAC), `security.py`, `otp.py` (OTP provider interface), `seed.py`, `files.py` (upload store), `notify.py` (in-app notifications as i18n key+params), `vision.py` (HTTP bridge to services/vision), `llm.py` (LLM interface + offline stub question generator), `ai.py` (Phase 4 `Tutor`/`Embedder` interfaces + offline stubs; `EDUNEST_AI_PROVIDER` other than `stub` -> 501), `rag.py` (chunk + embed + cosine retrieval over a user's notes), `learn.py` (mastery, weekly plan rules, SM-2), `ai_usage.py` (daily AI limit + call log), `assess.py` (grade scale, teacher-assignment check), `schemas.py`/`schemas_p2.py`/`schemas_p3.py`/`schemas_p4.py`, `routers/{auth,structure,people,attendance,timetable,homework,leave,idcard,notifications,quizzes,exams,reports,ai_chat,ai_learn}.py`
- `backend/tests/`: pytest (auth, CRUD/RBAC, attendance, timetable, homework, leave+ID card, assessment, `test_ai.py`, `test_tenant_isolation.py`)
- `frontend/src/`: `pages/{admin,teacher,student,parent,shared}` (shared = role-aware Homework/Leave/IdVerify/Quizzes/Exams/ReportCard), `components/{ui,layout,common}`, `lib/` (api client, auth store, queries), `i18n/locales/`
- `deploy/`: Dockerfiles + nginx. `docker-compose.yml` is **untested** (Docker not reachable from WSL).
- `docs/`: blueprint. `graphify-out/`: partial graph build, ignore.

## Run (WSL)
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed            # --reset wipes & reseeds (restores student DOB passwords)
.venv/bin/uvicorn app.main:app --reload --port 8000     # docs: :8000/docs
cd frontend && npm install && npm run dev               # http://localhost:5173
cd services/vision/backend && DEMO_MODE=1 python app.py # needs: pip install -r requirements-demo.txt
```
Checks: `cd backend && .venv/bin/python -m pytest -q` (98 pass) · `cd frontend && npm run build`.
Face mode needs the vision service (`EDUNEST_VISION_URL`, default :5000). A parallel scratch stack: `EDUNEST_DATABASE_URL=sqlite:///x.db EDUNEST_UPLOAD_DIR=./x-up uvicorn ... --port 8100` + `VITE_API_TARGET=http://127.0.0.1:8100 npx vite --port 5200`.
Don't `pkill -f uvicorn` in the same shell command as a restart (it kills the shell).
**After any backend change the server must be restarted**; run it with `--reload` so it happens automatically. A stale process was once mistaken for a routing bug (new routes 404 / old behaviour). When an endpoint "doesn't exist" or behaves like old code, check the process is fresh before debugging routes.

## Demo logins (school code `EDN01`; a second school `OTHER` exists only in tests)
| Role | Login ID | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Teacher | `T-001` (also T-002, T-003) | `teacher123` |
| Student | `EN-26-001`..`009` | DOB `DDMMYYYY`, e.g. `15082010`; **forced change on first login**, after which DOB stops working (reseed to reset) |
| Parent | mobile `9000000001` (2 kids; `…02`–`…08` 1 each) | OTP `000000` (dev stub, logged to console) |
| Super-admin | `super` (no school code, API only) | `super12345` |

## Rules that must keep holding
- Every school-owned table has `school_id` (`TenantMixin`); routes filter explicitly **and** `db.py` auto-filters via `session.info["school_id"]`. Any new table must use the mixin and get a case in `test_tenant_isolation.py`.
- RBAC via `require_roles(...)` plus row checks (teacher→own sections, student→self, parent→own children).
- Login limiter counts failures only (in-memory; move to Redis for prod). Tests set `EDUNEST_BCRYPT_ROUNDS=4`.
- All UI text via i18n keys in all three locale files. Notifications store a key + params (never English text); the UI translates.
- Uploads: never trust the client's content type (`files.save_upload` sniffs bytes), never serve from a public path, always check the same row-level access as the parent object.
- Leave visibility: admin sees student leave only once fully approved and can never decide it; class teacher sees it only after the parent step.
- Face attendance returns a proposal; only `PUT /attendance/sessions` writes records.

## Status
- **Built (Phase 1):** schema + seed, 4-role login (parent OTP, student forced pw change), RBAC, tenant isolation, CRUD for school/academic year/class/section/subject/teacher assignment/teacher/student/parent, role dashboards, en/te/hi UI.
- **Phase 2 DONE** (attendance, timetable, homework, leave, ID card):  attendance (manual sheet per section/date/period, parent in-app alerts on absent/late, admin summary + correction, student/parent history, face mode via vision bridge as proposal-then-confirm), timetable (admin periods + grid with teacher-clash check, teacher image/text upload, teacher personal timetable), homework (post/submit text+photo+PDF+voice file/review/return, parent status, admin counts), leave (student: parent -> class teacher -> admin view-only; teacher: admin), ID card + signed QR + staff verify, notification bell.
- **Not built, Phase 1 gaps:** bulk Excel import, student/teacher **edit** forms in UI (API PATCH exists), audit-log table, Alembic migrations (uses `create_all`), admin 2FA, super-admin UI, PWA/offline.
- **Not built, Phase 2 gaps:** leave quotas/custom types, SMS/WhatsApp/push, substitutions/swaps, timetable auto-generate, gate-scan log table, in-browser voice recorder & QR camera scan. Re-seed (`python -m app.seed --reset`) to get demo periods + a 10-A timetable on an older DB.
- **Phase 3 DONE** (assessment; Phases 1-3 all committed to git on `master`, commit `715c233`, working tree clean at that point): quiz builder (manual + PDF->draft via `llm.py`; only `StubGenerator`, an offline regex parser for numbered Qs with A)-D) options and `Answer:` lines, no real LLM; `EDUNEST_LLM_PROVIDER` other than `stub` -> 501), quiz player with server-side auto-grading (mcq/true_false/fill_blank; descriptive waits for teacher marks), one attempt per student, time limit enforced server-side (+60s grace; later = timed_out, zero score). Exams: Mock vs Main, teacher marks sheet, paper + staff-only answer key, publish (needs all marks/absent entered) -> students/parents notified; marks hidden until published. Report card `GET /report-card`: grade/overall from MAIN exams only; mock + quizzes shown as separate columns and on the progress graph; topic analysis from quiz answers (<50% = weak); homework completion.
- **Not built, Phase 3 gaps:** marks entry by Excel/photo-OCR/voice, AI grading of handwritten answers, real LLM/OCR (scanned PDFs return 422), question bank, quiz retakes, autosave of in-progress answers, hall tickets/seating/rooms, class-comparison + AI plain-language report, Phase 4 robo assistant on wrong answers. Frontend pages were build-checked only, not exercised in a browser.
- **Phase 4 DONE** (AI learning; uncommitted at time of writing): robo assistant under each WRONG quiz answer (Explain / Why was mine wrong / Next suggestion; cached per answer+mode+lang; Next picks same-topic auto-gradable questions from quizzes the student already submitted, never leaks keys before submit; `/ai/practice/{id}/check` is ungraded and does not feed mastery); AI Chat for students+teachers (private conversations, text + PDF/txt/image upload, retrieval over the user's own notes, answers carry sources); `topic_mastery` recomputed from quiz answers (weak < 50%, same as report card); weekly learning plan (rules: revise weak topic, practice 2 days later, flashcard days when due, rest Sunday; tick items; stale flag when weak set changes); SM-2 flashcards (from quiz mistakes, from notes, manual); teacher learning-gap report (`/teacher/gaps`); parent read-only Learning page. Per-user daily limit `EDUNEST_AI_DAILY_LIMIT` (default 100) + `ai_calls` log. `StubTutor`/`HashEmbedder` are offline and deterministic, NOT an LLM: stub answers chat only by quoting uploaded notes (else says it is in offline demo mode); the UI shows an "Offline demo AI" badge. Browser-verified with Playwright (student, teacher, parent, en/te).
- **Not built, Phase 4 gaps:** real LLM/embeddings/OCR (images + scanned PDFs are stored but unreadable), photo doubt, YouTube links, previous-year papers, summaries/mind-maps, voice, English tutor, content-safety filter, LLM-written plan notes, practice answers do not update mastery, pgvector (embeddings are JSON, cosine in Python), AI chat for admin/parent.
- **Known, pre-existing:** the shared top bar overflows ~7px horizontally at 390px width on every page.
- **Next:** later phases (blueprint §18: communication, fees/transport, advanced).
