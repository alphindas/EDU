# EduNest 2.0 — AI-powered smart school portal

**Learn · Explore · Innovate · Grow.** Four role portals (Student, Teacher, Parent, Admin) and **one** shared AI engine, **CHITTI 2.0**, with different modes, knowledge and permissions per role. Light, kid-friendly design with an original robot mascot, 5 UI languages (English, తెలుగు, हिन्दी, മലയാളം, தமிழ்), gamification, analytics and safety built in.

| Part | Stack | Port |
|---|---|---|
| `backend/` | FastAPI · SQLAlchemy 2 · SQLite (Postgres-ready) · JWT + RBAC · multi-tenant · WebSockets | 8000 |
| `frontend/` | React 18 · Vite · TypeScript · Tailwind · i18next (5 languages) · TanStack Query · Recharts | 5173 |
| `services/vision/` | CerebroMark Flask smart-attendance (face recognition) — unchanged | 5000 |

---

## 1. Quick start (Linux / macOS / WSL)

Needs **Python 3.11+** and **Node 18+**.

```bash
unzip EduNest-2.0.zip && cd edunest
./run.sh            # first run: creates venv, installs everything, seeds demo data, starts API + web app
```
Open **http://localhost:5173**. Stop with `Ctrl+C`. Re-run `./run.sh` any time (`./run.sh --reset` rebuilds the demo data).

### Manual steps (Windows PowerShell or if you prefer)
```bash
# terminal 1 — API (docs at http://localhost:8000/docs)
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip install -r requirements.txt
cp .env.example .env                                # optional: add an AI key (see §3)
.venv/bin/python -m app.seed --reset                # demo school + illustrative activity data
.venv/bin/uvicorn app.main:app --reload --port 8000

# terminal 2 — web app
cd frontend
npm install
npm run dev                                         # http://localhost:5173

# terminal 3 (optional) — face-recognition attendance
cd services/vision/backend && pip install -r requirements-demo.txt && DEMO_MODE=1 python app.py
```

**Optional for photo doubts (OCR):** install Tesseract — Ubuntu/WSL `sudo apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-tel tesseract-ocr-mal tesseract-ocr-tam`, Windows: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki). Without it, students can still type the question.

**Docker:** `docker compose up --build` (web :5173, API :8000, vision :5000).

## 2. Demo logins (school code `EDN01`)

| Role | Login | Password |
|---|---|---|
| Student | `EN-26-001` (Aarav, 10-A) … `EN-26-009` | date of birth `DDMMYYYY`, e.g. `15082010` → **must set a new password on first login** |
| Teacher | `T-001` (Maths, class teacher 10-A) · `T-002` · `T-003` (also the **counsellor**) | `teacher123` |
| Parent | mobile `9000000001` (2 children) · `…02`–`…08` | OTP `000000` (dev mode) |
| Admin | `admin` | `admin123` |

The login page has one-click **Demo logins** buttons. `EN-26-008`'s parent has **not** given AI consent, to demo the consent flow. All activity data (attendance, quizzes, XP, bus…) is **illustrative**, generated relative to today.

## 3. CHITTI 2.0 AI engine

Works **out of the box offline** (no key, no internet): built-in starter topics with practice MCQs, step-by-step maths solver (equations, %, arithmetic), English grammar/fluency coach, riddles, hybrid search over the school library with source citations, OCR photo doubts. It says *"I'm not sure"* rather than guessing.

For full answers on any topic, in any of the 5 languages, add a key to `backend/.env`:

```ini
# OpenAI (or any OpenAI-compatible API: Groq, OpenRouter, Together, local Ollama…)
EDUNEST_AI_PROVIDER=openai
EDUNEST_AI_API_KEY=sk-...
EDUNEST_AI_MODEL=gpt-4o-mini
# EDUNEST_AI_BASE_URL=https://api.groq.com/openai/v1   (or http://localhost:11434/v1 for Ollama)
# EDUNEST_AI_EMBED_MODEL=text-embedding-3-small         (real embeddings for RAG)

# …or Google Gemini
EDUNEST_AI_PROVIDER=gemini
EDUNEST_AI_API_KEY=AIza...
EDUNEST_AI_MODEL=gemini-1.5-flash
```
Restart the API. If the provider fails mid-lesson, CHITTI falls back to offline mode automatically. Voice (speech-to-text + read-aloud) uses the browser's Web Speech API — best in **Chrome/Edge**; Telugu/Hindi/Tamil/Malayalam voices depend on the device.

| Role | CHITTI modes | Knowledge it may use |
|---|---|---|
| Student | Study Buddy, Doubt Solver, English Chitti, Aptitude, Puzzle Master, Career Chitti | school library for own class + own uploaded notes |
| Teacher | Lesson planner, Study Buddy, Doubt Solver | whole library + own notes |
| Parent | Parent helper | child's class syllabus only |
| Admin | Lesson planner, Study Buddy | whole library |

## 4. What's in each portal

**Student** — home dashboard (streak, XP, attendance, due work, quests, rotating welcome) · CHITTI chat with voice, file/photo upload, history, read-aloud · Topic explorer (explanation + YouTube links + practice quiz) · Photo doubt (OCR → steps → "practise similar") · quizzes with the robot helper on wrong answers (explain / why wrong / next) · mock & main exams · weak-topic weekly plan · spaced-repetition flashcards · **Knowledge Adventure** (5 worlds with stages, daily quests, boss challenges, mystery box, 12 badges, levels, coins, house teams, opt-in leaderboard, CHITTI dress-up shop, real-world missions) · **Brain Gym** (8 skills, adaptive puzzles, *Learning Growth Score — not IQ*) · **English Chitti** (speak/write/pronounce/interview, private fluency graph) · **Career Lab** (interest quiz → career directions + roadmaps, STEM lab, code quest, scholarship finder) · Library (chapters, in-book search, bookmarks, completion, AI summary + mind-map, offline download) · projects + portfolio · doubt board · teacher messages · personal growth (reflections, kindness missions, decision scenarios) · anonymous counselling · live bus · leave · ID card.

**Teacher** — class insights (averages, topic mastery, most-missed questions, completion, improvement, students needing a check-in, **one-click revision quiz**, CHITTI oversight) · attendance (manual + face) · PDF→quiz builder · exams & marks · homework · library upload · announcements · messages · forum moderation · counselling inbox (if counsellor) · leave.

**Parent** — children overview · leave from a plain message (*"My child will not attend tomorrow due to a family function"* → pending request to class teacher, **never auto-approved**) · AI consent switch · Parent CHITTI · growth & progress · attendance, homework, quizzes, exams, report card · live bus · messages.

**Admin** — school intelligence (filters, section/subject comparisons, growth over time, pattern detection with supportive actions — never labels) · people & structure · transport (routes, buses, GPS device tokens, stop assignment) · safety & audit (audit log, counsellor assignment, AI oversight) · announcements · leave · everything from Phases 1–4.

## 5. Architecture & safety notes
- **Multi-tenant + RBAC:** every school table has `school_id`; a session-level guard filters every query. `tests/test_tenant_isolation.py` populates *every* table (incl. all 2.0 tables) in two schools and proves no leaks.
- **Privacy:** only academic text is sent to AI providers (never names/IDs). Students need parent consent for AI. Counselling messages are readable only by staff flagged as counsellors; anonymous threads hide identity. Reflections and English practice text are private to the student. Leaderboards are opt-in; teams count everyone's effort.
- **Rate limits:** daily AI limit + per-minute burst limit per user. **Audit log** of every mutating request and every AI question.
- **Uploads:** type sniffed from bytes, size-capped, stored outside the web root, served only through permission checks.
- **Realtime:** `/api/ws` (DMs/notifications) and `/api/ws/bus/{id}` (live bus). Single-process in-memory hub; use Redis pub/sub for multiple workers.
- **Database:** SQLite by default. For PostgreSQL set `EDUNEST_DATABASE_URL=postgresql+psycopg://…` (`pip install "psycopg[binary]"`). Full DDL: `backend/migrations/001_initial_postgres.sql` (regenerate with `python -m scripts.export_schema`). Embeddings are stored as JSON with hybrid BM25 + cosine + rerank; swap to pgvector for large libraries.

## 6. Tests
```bash
cd backend && .venv/bin/python -m pytest -q     # 134 tests (104 original + 30 EduNest 2.0)
cd frontend && npm run build && npm run lint
```
See `docs/TEST_PLAN.md` for the manual click-through plan.

## 7. Known limits (honest list)
- Offline CHITTI covers 16 starter topics + library material; real breadth needs an API key. Offline explanations are English; UI is fully translated.
- Voice language support depends on the browser/device. Interactive AR/3D models, SMS/WhatsApp alerts, fee payments and a native mobile app are not included.
- Scholarship finder uses **demo** eligibility rules and links to the official National Scholarship Portal.
- Bus position is simulated from the route timetable until a GPS device posts real locations.


## CHITTI robot, voice talk and colour themes

- **Robot picture**: CHITTI everywhere (header, floating button, chat, login, celebrations) uses `frontend/src/assets/chitti.webp` (full body) and `chitti-head.webp` (square face crop). To change it, replace those two files (a higher-resolution picture looks sharper) and rebuild. Shop items (hat, pet, colour ring) still appear on top.
- **Talk with CHITTI**: open CHITTI, then the **Talk** tab (or press **Start talking**). Speak, CHITTI answers out loud, then listens again, like a phone call. Tap CHITTI or **Stop** to interrupt. Works in Chrome and Edge (needs microphone permission); other browsers can use "Type instead". Voice follows the app language (English, Telugu, Hindi, Malayalam, Tamil); Indian-language voices depend on what is installed on the device. Greetings, thanks, jokes and "how are you" are answered even with no AI key; with an AI key CHITTI gives short spoken-style answers.
- **12 colour themes**: palette icon in the top bar. Ocean (sky blue + navy) is the default; also Sky, Mint, Forest, Teal, Indigo, Violet, Lavender, Rose, Coral, Sunset, Mango, plus a Light/Dark switch. Saved per device. Add more in `frontend/src/lib/theme.ts` and `index.css`.
- Demo student passwords are the date of birth (DDMMYYYY) and must be changed on first login.
