# EduNest 2.0 — Test plan

## Automated (run before every release)
| Suite | Command | Covers |
|---|---|---|
| Backend | `cd backend && python -m pytest -q` | 134 tests: auth, RBAC, tenant isolation of **every** table, attendance, timetable, homework, leave, quizzes/exams, AI tutor, and `test_v2.py` (CHITTI consent & modes, topic search, photo doubt + OCR, burst limit, oversight, XP/streak/badges, puzzle token replay/forgery, adaptive difficulty, opt-in leaderboard, boss & mystery limits, English coach, career, private reflections, library class scope & citations, announcement targeting, DM pairs, forum moderation, counselling privacy, projects/portfolio, transport + websockets, teacher/admin insights, parent leave-from-message, audit log, cross-school isolation) |
| Frontend | `cd frontend && npm run build && npm run lint` | TypeScript types, production bundle, lint |
| i18n | every key exists in en/te/hi/ml/ta with matching `{{placeholders}}` (1,252 keys each) | |

## Manual click-through (≈20 min, fresh `python -m app.seed --reset`)
**Student `EN-26-001` / `15082010`**
1. First login forces a new password. Home shows greeting, streak, XP, attendance ring, due exam, quests, announcements.
2. Daily check-in (if available) → "+XP" pill; badge pop-up when a badge unlocks.
3. CHITTI → Chat: "Solve 2x + 3 = 11" → 4 numbered steps, answer x = 4. Mic button transcribes (Chrome). Read aloud speaks.
4. Topic explorer: "Photosynthesis" → explanation, example, key points, YouTube links, "Practise 4 questions" quiz with explanations.
5. Photo doubt: upload a photo of "3x + 6 = 21" → text read, steps, "Practise similar questions".
6. Adventure: quests progress, open mystery box (once/day), boss challenge (5 puzzles; memory puzzles flash then hide), buy & wear a shop item, toggle "Show me" on leaderboard.
7. Brain Gym: play a skill; difficulty rises after 4/5 right; score ring updates; "not an IQ test" note visible.
8. English Chitti: write "he don't like it" → corrected + reasons; Pronounce tab scores words.
9. Career Lab: answer ≥8 questions → 3 interest areas with careers + roadmap + "not predictions" note; scholarship finder links to official portal.
10. Library: open notes → chapters, search "straight", mark done (+XP), Summarise → bullets + mind-map.
11. Quizzes: answer wrongly → robot helper Explain / Why wrong / Next.
12. Forum post, Projects (start one), Growth reflection, Counselling (anonymous), Bus page shows route + ETA.
13. Switch language to తెలుగు, हिन्दी, മലയാളം, தமிழ் — all menus/pages translate; refresh keeps the choice.

**Parent `9000000001` / OTP `000000`**
14. Home: both children with level/streak/attendance. Leave box: type *"Aarav will not attend tomorrow due to a family function"* → Prepare → correct child/date/type → Send. Status = waiting for class teacher (never approved automatically).
15. Turn CHITTI permission off for Aarav → as Aarav, CHITTI shows "sleeping" screen. Turn it back on.
16. Growth & progress, Parent CHITTI ("Explain the water cycle simply"), Bus, Messages to teacher.

**Teacher `T-001` / `teacher123`**
17. Leave: approve the parent-created request → parent notified.
18. Class insights 10-A: summary cards, topic chart, most-missed, students with kind signals; "Make revision quiz" → draft quiz appears in Quizzes.
19. CHITTI oversight tab lists student questions. Library upload a text/PDF with "Chapter 1…" lines → students see it.
20. Announcement to 10-A students → student sees it + notification. Messages: reply live (WebSocket) to a student.

**Teacher `T-003`** — Counselling inbox shows the anonymous thread (no name). `T-002` gets "only counsellors".

**Admin `admin` / `admin123`**
21. School intelligence: cards, patterns with supportive actions, charts; change class/subject/date filters.
22. Transport: add route/bus/assignment; copy device token; `curl -X POST localhost:8000/api/transport/vehicles/1/location -H "X-Device-Token: …" -H "Content-Type: application/json" -d '{"lat":17.43,"lng":78.41}'` → parent bus page switches from "Demo position" to live.
23. Safety & audit: audit rows for every change + AI questions; toggle counsellor flags.

**Accessibility / devices**: keyboard-only navigation (skip link, focus rings), 390 px mobile (bottom tabs + More sheet), dark-mode toggle, `prefers-reduced-motion` stops animations, print the report card.
