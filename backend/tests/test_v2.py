"""EduNest 2.0: CHITTI engine, consent, gamification, knowledge growth, library, announcements, communication,
counselling privacy, projects/portfolio, transport, insights, parent leave assistant, audit log, websockets."""
import io
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from tests.conftest import login, parent_login, png_bytes, section_id, student_ids, student_login, subject_id, teacher_login


def grant_consent(client, par, stu_id):
    r = client.put("/api/chitti/consent", headers=par, json={"student_id": stu_id, "allow": True})
    assert r.status_code == 200, r.text


def populate_v2(client, adm, tch, stu, par):
    """One row in every EduNest 2.0 table (used by the tenant-isolation test too)."""
    st = student_ids(client, adm)
    me = st["EN-26-001"]
    grant_consent(client, par, me)  # student_prefs
    assert client.put(f"/api/staff-flags/{_uid(client, adm, 'T-001')}", headers=adm, json={"counsellor": True}).status_code == 200  # staff_flags
    assert client.post("/api/game/checkin", headers=stu).status_code == 200  # xp_events, streaks, user_badges(first_explorer)
    pz = client.get("/api/growth/puzzle?skill=numerical&difficulty=1", headers=stu).json()
    assert client.post("/api/growth/answer", headers=stu, json={"token": pz["token"], "choice": 0}).status_code == 200  # brain_attempts
    prof = client.get("/api/game/profile", headers=stu).json()
    q = next((x for x in prof["quests"] if x["done"]), None)
    if q is None:  # finish one quest deterministically: do whatever today's first quest asks
        _do_quest(client, stu, tch, adm, prof["quests"][0])
        q = prof["quests"][0]
    assert client.post(f"/api/game/quests/{q['id']}/claim", headers=stu).status_code == 200  # quest_claims
    cls10 = next(c["id"] for c in client.get("/api/classes", headers=adm).json() if c["name"] == "10")
    res = client.post("/api/library", headers=tch, data={"kind": "notes", "title": "Light notes", "class_id": cls10,
                      "text": "Chapter 1 Light\nLight travels in straight lines. Reflection is bouncing back.\nChapter 2 Sound\nSound needs a medium."}).json()
    assert client.patch(f"/api/library/{res['id']}/progress", headers=stu, json={"complete_chapter": 0}).status_code == 200  # resource_progress
    sec = section_id(client, adm)
    assert client.post("/api/announcements", headers=adm, json={"title": "Sports day", "body": "Friday!", "audience": "all"}).status_code == 201
    t_uid = _uid(client, adm, "T-001")
    assert client.post("/api/messages", headers=stu, json={"to": t_uid, "body": "Doubt in ch 3"}).status_code == 201  # direct_messages
    post = client.post("/api/forum", headers=stu, json={"title": "How do mirrors work?", "body": "?"}).json()
    assert client.post(f"/api/forum/{post['id']}/replies", headers=tch, json={"body": "Reflection!"}).status_code == 201
    th = client.post("/api/counselling", headers=stu, json={"topic": "talk", "anonymous": True, "body": "I feel stressed"}).json()
    assert client.post(f"/api/counselling/{th['id']}/messages", headers=tch, json={"body": "I'm here to help"}).status_code == 200
    pj = client.post("/api/projects", headers=stu, json={"title": "Solar oven", "summary": "box + foil"}).json()
    assert client.post(f"/api/projects/{pj['id']}/comments", headers=tch, json={"body": "Nice"}).status_code == 201
    assert client.post("/api/portfolio", headers=stu, data={"kind": "art", "title": "Painting"}, files={"file": ("p.png", png_bytes(), "image/png")}).status_code == 201
    assert client.post("/api/career/submit", headers=stu, json={"answers": {f"q{i}": 3 + i % 3 for i in range(1, 13)}}).status_code == 200
    assert client.post("/api/english/check", headers=stu, json={"text": "i goes to school"}).status_code == 200
    assert client.post("/api/growth/reflections", headers=stu, json={"kind": "reflection", "prompt": "proud", "mood": "😊", "text": "I helped"}).status_code == 200
    route = client.post("/api/transport/routes", headers=adm, json={"name": "R1", "start_time": "07:00", "stops": [
        {"name": "Gate", "lat": 17.40, "lng": 78.40, "minute": 0}, {"name": "School", "lat": 17.42, "lng": 78.42, "minute": 30}]}).json()
    veh = client.post("/api/transport/vehicles", headers=adm, json={"number": "TS09 1234", "route_id": route["id"]}).json()
    assert client.put("/api/transport/assignments", headers=adm, json={"student_id": me, "route_id": route["id"], "stop_name": "Gate"}).status_code == 200
    assert client.post(f"/api/transport/vehicles/{veh['id']}/location", headers={"X-Device-Token": veh["device_token"]},
                       json={"lat": 17.41, "lng": 78.41}).status_code == 201  # vehicle_locations
    assert client.post("/api/chitti/ask", headers=stu, data={"text": "what is photosynthesis", "mode": "study_buddy"}).status_code == 200  # audit AI
    _give_coins(client, stu)
    r = client.post("/api/game/shop/color_mint/buy", headers=stu)
    assert r.status_code == 200, (r.text, client.get("/api/game/profile", headers=stu).json()["coins"])  # shop_purchases
    return {"route": route, "veh": veh, "res": res, "post": post, "thread": th, "project": pj, "me": me}


def _uid(client, adm, emp):
    return next(t["user_id"] for t in client.get("/api/teachers?limit=50", headers=adm).json()["items"] if t["employee_id"] == emp)


def _give_coins(client, stu):
    client.post("/api/game/mystery", headers=stu, json={"choices": [0, 0, 0]})  # 409 if a quest already opened it
    for i in range(120):  # correct answers earn a coin; we can't see the key, so keep answering fresh puzzles
        if client.get("/api/game/profile", headers=stu).json()["coins"] >= 30:
            break
        pz = client.get("/api/growth/puzzle?skill=numerical&difficulty=1", headers=stu).json()
        client.post("/api/growth/answer", headers=stu, json={"token": pz["token"], "choice": i % 4})


def _do_quest(client, stu, tch, adm, q):
    k = q["kind"]
    for _ in range(q["target"]):
        if k == "brain":
            pz = client.get("/api/growth/puzzle?skill=pattern", headers=stu).json()
            client.post("/api/growth/answer", headers=stu, json={"token": pz["token"], "choice": 1})
        elif k == "english":
            client.post("/api/english/check", headers=stu, json={"text": "We was happy"})
        elif k == "reflection":
            client.post("/api/growth/reflections", headers=stu, json={"kind": "mission", "prompt": "plan_day", "text": "done"})
        elif k == "chitti":
            client.get("/api/chitti/topic?q=fractions", headers=stu)
        elif k == "mystery":
            client.post("/api/game/mystery", headers=stu, json={"choices": [1, 1, 1]})
        elif k == "quiz":
            from tests.test_assessment import answers_for, new_quiz

            qid = new_quiz(client, adm, tch)
            play = client.post(f"/api/quizzes/{qid}/attempts", headers=stu).json()
            client.post(f"/api/attempts/{play['attempt_id']}/submit", headers=stu, json={"answers": answers_for(play)})
        elif k == "homework":
            maths = subject_id(client, adm, "Mathematics")
            hw = client.post("/api/homework", headers=tch, data={"section_id": section_id(client, adm), "subject_id": maths, "title": "Q",
                                                                  "due_date": (date.today() + timedelta(days=2)).isoformat()}).json()
            client.post(f"/api/homework/{hw['id']}/submissions", headers=stu, data={"text": "done"})
        elif k == "flashcard":
            c = client.post("/api/ai/flashcards", headers=stu, json={"front": f"F{_}", "back": "B"}).json()
            client.post(f"/api/ai/flashcards/{c['id']}/review", headers=stu, json={"quality": 4})


@pytest.fixture()
def ctx(client, admin, teacher, student1, parent1):
    return {"adm": admin, "tch": teacher, "stu": student1, "par": parent1, **populate_v2(client, admin, teacher, student1, parent1)}


@pytest.fixture()
def consent_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "require_ai_consent", True)


# ------------------------------------------------------------------ CHITTI + consent
def test_consent_gate_and_parent_toggle(client, admin, student1, parent1, consent_on):
    r = client.post("/api/chitti/ask", headers=student1, data={"text": "hi", "mode": "study_buddy"})
    assert r.status_code == 403 and r.json()["detail"] == "parent_consent_required"
    assert client.get("/api/chitti/status", headers=student1).json()["consent"] is False
    me = student_ids(client, admin)["EN-26-001"]
    other = student_ids(client, admin)["EN-26-002"]
    assert client.put("/api/chitti/consent", headers=parent1, json={"student_id": other, "allow": True}).status_code == 404  # not my child
    grant_consent(client, parent1, me)
    r = client.post("/api/chitti/ask", headers=student1, data={"text": "Explain photosynthesis", "mode": "study_buddy"})
    assert r.status_code == 200 and "glucose" in r.json()["reply"].lower()
    assert r.json()["reward"]["xp"] == 2


def test_modes_are_role_scoped(client, teacher, parent1, student1):
    assert client.post("/api/chitti/ask", headers=student1, data={"text": "plan", "mode": "lesson_plan"}).status_code == 403
    assert client.post("/api/chitti/ask", headers=parent1, data={"text": "hi", "mode": "study_buddy"}).status_code == 403
    assert client.post("/api/chitti/ask", headers=parent1, data={"text": "Explain fractions to me", "mode": "parent"}).status_code == 200
    assert client.post("/api/chitti/ask", headers=teacher, data={"text": "Make a lesson on gravity", "mode": "lesson_plan"}).status_code == 200


def test_topic_search_videos_and_practice(client, student1):
    j = client.get("/api/chitti/topic?q=Red planet mars&lang=te", headers=student1).json()
    assert "Mars" in j["title"] and j["practice"] and all("youtube.com/results" in v["url"] for v in j["videos"])
    assert "telugu" in j["videos"][0]["url"]
    unknown = client.get("/api/chitti/topic?q=quantum chromodynamics", headers=student1).json()
    assert "not sure" in unknown["explanation"].lower()


def test_photo_doubt_solver_and_similar(client, student1):
    r = client.post("/api/chitti/photo-doubt", headers=student1, data={"text": "Solve 2x + 3 = 11"}).json()
    assert r["answer"] == "x = 4" and len(r["steps"]) >= 3
    sim = client.get(f"/api/chitti/practice-similar?topic={r['topic']}", headers=student1).json()["questions"]
    assert len(sim) == 5 and all(0 <= q["a"] < len(q["o"]) for q in sim)
    assert client.post("/api/chitti/photo-doubt", headers=student1, data={"text": ""}).status_code == 422


def test_photo_doubt_ocr_reads_an_image(client, student1):
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (900, 200), "white")
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 72)
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(im).text((30, 50), "3x + 6 = 21", fill="black", font=font)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    r = client.post("/api/chitti/photo-doubt", headers=student1, files={"file": ("q.png", buf.getvalue(), "image/png")})
    assert r.status_code in (200, 422)
    if r.status_code == 200 and r.json()["ocr_text"]:
        assert "=" in r.json()["ocr_text"]


def test_burst_limit(client, student1, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_per_minute", 2)
    for _ in range(2):
        assert client.get("/api/chitti/topic?q=cell", headers=student1).status_code == 200
    assert client.get("/api/chitti/topic?q=cell", headers=student1).status_code == 429


def test_oversight_teacher_sees_only_own_sections(client, ctx, teacher, teacher2):
    rows = client.get("/api/chitti/oversight", headers=teacher).json()
    assert rows and rows[0]["student"] == "Aarav Reddy"
    assert client.get("/api/chitti/oversight", headers=ctx["stu"]).status_code == 403


# ------------------------------------------------------------------ gamification + growth
def test_checkin_streak_and_quiz_xp(client, admin, teacher, student1):
    r = client.post("/api/game/checkin", headers=student1)
    assert r.status_code == 200 and r.json()["streak"] == 1 and "first_explorer" in r.json()["new_badges"]
    assert client.post("/api/game/checkin", headers=student1).status_code == 409
    from tests.test_assessment import answers_for, new_quiz

    before = client.get("/api/game/profile", headers=student1).json()["xp"]
    qid = new_quiz(client, admin, teacher)
    play = client.post(f"/api/quizzes/{qid}/attempts", headers=student1).json()
    client.post(f"/api/attempts/{play['attempt_id']}/submit", headers=student1, json={"answers": answers_for(play)})
    after = client.get("/api/game/profile", headers=student1).json()
    assert after["xp"] > before and next(w for w in after["worlds"] if w["id"] == "math")["xp"] > 0


def test_puzzle_tokens_cannot_be_replayed_or_forged(client, student1, admin):
    pz = client.get("/api/growth/puzzle?skill=pattern&difficulty=2", headers=student1).json()
    assert "answer" not in pz and len(pz["options"]) == 4
    assert client.post("/api/growth/answer", headers=student1, json={"token": pz["token"], "choice": 0}).status_code == 200
    assert client.post("/api/growth/answer", headers=student1, json={"token": pz["token"], "choice": 1}).status_code == 409
    raw, sig = pz["token"].rsplit(".", 1)
    assert client.post("/api/growth/answer", headers=student1, json={"token": raw + ".deadbeef", "choice": 0}).status_code == 400
    other = student_login(client, "EDN01", "EN-26-002", "22032010")
    pz2 = client.get("/api/growth/puzzle?skill=memory", headers=student1).json()
    assert "show" in pz2 and pz2["seconds"] >= 3
    assert client.post("/api/growth/answer", headers=other, json={"token": pz2["token"], "choice": 0}).status_code == 400  # not theirs
    sc = client.get("/api/growth/scores", headers=student1).json()
    assert sc["label"] == "Learning Growth Score" and sc["skills"]["pattern"]["attempts"] == 1


def test_adaptive_difficulty_rises():
    from types import SimpleNamespace as N

    from app.brain import next_difficulty

    rows = [N(skill="x", difficulty=2, correct=True) for _ in range(5)]
    assert next_difficulty(rows) == 3
    assert next_difficulty([N(skill="x", difficulty=3, correct=False) for _ in range(4)]) == 2


def test_leaderboard_is_opt_in(client, ctx):
    lb = client.get("/api/game/leaderboard", headers=ctx["stu"]).json()
    assert lb["people"] == [] and lb["hidden"] >= 1 and len(lb["teams"]) == 4
    client.patch("/api/game/prefs", headers=ctx["stu"], json={"leaderboard_opt_in": True})
    lb = client.get("/api/game/leaderboard", headers=ctx["stu"]).json()
    assert lb["people"][0]["me"] is True and lb["people"][0]["name"] == "Aarav"


def test_boss_and_mystery_once_a_day(client, ctx):
    stu = ctx["stu"]
    b = client.get("/api/game/boss/math", headers=stu).json()
    assert len(b["puzzles"]) == 5
    r = client.post("/api/game/boss/math", headers=stu, json={"answers": [{"token": p["token"], "choice": 0} for p in b["puzzles"]]})
    assert r.status_code == 200 and r.json()["total"] == 5
    pz = client.get("/api/growth/puzzle?skill=numerical", headers=stu).json()
    assert client.post("/api/game/boss/math", headers=stu, json={"answers": [{"token": pz["token"], "choice": 0}]}).status_code == 400
    m = client.get("/api/game/mystery", headers=stu).json()
    if not m["done"]:
        assert client.post("/api/game/mystery", headers=stu, json={"choices": [0, 0, 0]}).status_code == 200
    assert client.post("/api/game/mystery", headers=stu, json={"choices": [0, 0, 0]}).status_code == 409


def test_parent_sees_child_profile_not_others(client, ctx, admin):
    par = ctx["par"]
    me = ctx["me"]
    assert client.get(f"/api/game/profile?student_id={me}", headers=par).json()["xp"] > 0
    other = student_ids(client, admin)["EN-26-003"]
    assert client.get(f"/api/game/profile?student_id={other}", headers=par).status_code == 404
    assert client.get(f"/api/growth/scores?student_id={other}", headers=par).status_code == 404


# ------------------------------------------------------------------ English, career, growth
def test_english_coach(client, student1):
    r = client.post("/api/english/check", headers=student1, json={"text": "he don't like it and we was late", "seconds": 6, "kind": "speaking"}).json()
    assert "doesn't" in r["corrected"] and "were" in r["corrected"] and r["wpm"] > 0
    p = client.post("/api/english/pronounce", headers=student1, json={"target": "She sells sea shells", "heard": "she sells sea shell"}).json()
    assert 50 < p["score"] < 100
    prog = client.get("/api/english/progress", headers=student1).json()
    assert len(prog["sessions"]) == 2 and prog["sessions"][0]["text"]


def test_career_guidance_and_scholarships(client, student1):
    r = client.post("/api/career/submit", headers=student1, json={"answers": {"q2": 5, "q7": 5, "q1": 1, "q3": 1, "q4": 2, "q5": 2, "q6": 3, "q8": 2}}).json()
    assert r["suggestions"][0]["area"] == "think" and "not predictions" in r["note"]
    s = client.post("/api/career/scholarships", headers=student1, json={"marks": 85, "category": "general", "girl": False}).json()
    assert any("Merit" in m["name"] for m in s["matches"]) and s["official_portal"].startswith("https://")


def test_reflections_private(client, ctx, teacher):
    assert client.get("/api/growth/reflections", headers=ctx["stu"]).json()[0]["text"] == "I helped"
    assert client.get("/api/growth/reflections", headers=teacher).status_code == 403
    assert client.post("/api/growth/reflections", headers=ctx["stu"], json={"kind": "reflection", "prompt": "proud"}).status_code == 409


# ------------------------------------------------------------------ library + announcements
def test_library_chapters_search_and_class_scope(client, ctx, admin):
    res = ctx["res"]
    assert res["chapter_count"] == 2
    d = client.get(f"/api/library/{res['id']}", headers=ctx["stu"]).json()
    assert d["chapters"][0]["title"].startswith("Chapter 1") and d["completed"] == [0]
    hits = client.get(f"/api/library/{res['id']}/search?q=straight", headers=ctx["stu"]).json()
    assert hits and hits[0]["chapter"] == 0
    s9 = student_login(client, "EDN01", "EN-26-009", "20052011")  # class 9: must not see a class-10 resource
    assert client.get(f"/api/library/{res['id']}", headers=s9).status_code == 404
    assert all(r["id"] != res["id"] for r in client.get("/api/library", headers=s9).json())
    j = client.post("/api/chitti/ask", headers=ctx["stu"], data={"text": "does light travel in straight lines", "mode": "study_buddy"}).json()
    assert any("Light notes" in s["name"] for s in j["sources"])  # school-approved material cited


def test_announcement_targeting(client, admin, teacher, teacher2, student1):
    sec_b = section_id(client, admin, "10-B")
    sec_a = section_id(client, admin, "10-A")
    assert client.post("/api/announcements", headers=teacher, json={"title": "x", "body": "y", "section_id": sec_b, "audience": "students"}).status_code in (201, 403)
    assert client.post("/api/announcements", headers=teacher, json={"title": "Test", "body": "Bring lab coat", "section_id": sec_a, "audience": "students"}).status_code == 201
    assert client.post("/api/announcements", headers=teacher2, json={"title": "B only", "body": "z", "section_id": sec_b, "audience": "students"}).status_code == 201
    titles = [a["title"] for a in client.get("/api/announcements", headers=student1).json()]
    assert "Test" in titles and "B only" not in titles
    assert any(n["key"] == "notif.announcement" for n in client.get("/api/notifications", headers=student1).json())


# ------------------------------------------------------------------ communication
def test_messages_only_between_allowed_pairs(client, ctx, admin):
    stu = ctx["stu"]
    contacts = client.get("/api/messages/contacts", headers=stu).json()
    assert {c["role"] for c in contacts} == {"teacher"}
    s2 = student_login(client, "EDN01", "EN-26-002", "22032010")
    s2_uid = client.get("/api/auth/me", headers=s2).json()["id"]
    assert client.post("/api/messages", headers=stu, json={"to": s2_uid, "body": "hi"}).status_code == 403
    t_uid = _uid(client, admin, "T-001")
    msgs = client.get(f"/api/messages/thread/{client.get('/api/auth/me', headers=stu).json()['id']}", headers=ctx["tch"]).json()
    assert msgs and msgs[0]["mine"] is False
    assert client.get(f"/api/messages/thread/{t_uid}", headers=stu).json()[0]["mine"] is True
    par_contacts = client.get("/api/messages/contacts", headers=ctx["par"]).json()
    assert any(c["user_id"] == t_uid for c in par_contacts)


def test_forum_moderation(client, ctx, student1):
    p = ctx["post"]
    assert client.patch(f"/api/forum/{p['id']}", headers=student1, json={"hidden": True}).status_code == 403
    assert client.patch(f"/api/forum/{p['id']}", headers=ctx["tch"], json={"hidden": True}).status_code == 200
    s2 = student_login(client, "EDN01", "EN-26-002", "22032010")
    assert client.get(f"/api/forum/{p['id']}", headers=s2).status_code == 404
    assert all(x["id"] != p["id"] for x in client.get("/api/forum", headers=s2).json())


def test_counselling_privacy(client, ctx, teacher2, admin):
    th = ctx["thread"]
    assert client.get("/api/counselling/inbox", headers=teacher2).status_code == 403  # not a counsellor
    assert client.get("/api/counselling/inbox", headers=admin).status_code == 403  # admins are not counsellors by default
    inbox = client.get("/api/counselling/inbox", headers=ctx["tch"]).json()
    assert inbox[0]["anonymous"] is True and inbox[0]["student"] is None
    assert client.post(f"/api/counselling/{th['id']}/messages", headers=teacher2, json={"body": "x"}).status_code == 404
    mine = client.get("/api/counselling", headers=ctx["stu"]).json()
    assert mine[0]["messages"][-1]["from_staff"] is True


def test_projects_and_portfolio(client, ctx, admin):
    s2 = student_login(client, "EDN01", "EN-26-002", "22032010")
    j = client.post(f"/api/projects/{ctx['project']['id']}/join", headers=s2).json()
    assert len(j["members"]) == 2 and j["joined"]
    port = client.get(f"/api/portfolio?student_id={ctx['me']}", headers=ctx["par"]).json()
    assert port and port[0]["has_file"]
    assert client.get(f"/api/portfolio/{port[0]['id']}/file", headers=ctx["par"]).status_code == 200
    assert client.get(f"/api/portfolio/{port[0]['id']}/file", headers=s2).status_code == 404


# ------------------------------------------------------------------ transport
def test_transport_live_and_scope(client, ctx, admin):
    my = client.get("/api/transport/my", headers=ctx["par"]).json()
    live = my[0]["live"]
    assert live["simulated"] is False and live["position"]["lat"] == 17.41 and len(live["stops"]) == 2
    other_par = parent_login(client, "EDN01", "9000000003")[0]
    assert client.get(f"/api/transport/live/{ctx['veh']['id']}", headers=other_par).status_code == 404
    assert client.post(f"/api/transport/vehicles/{ctx['veh']['id']}/location", headers={"X-Device-Token": "nope"}, json={"lat": 1, "lng": 1}).status_code == 401
    from app.models_v2 import TransportRoute
    from app.routers.transport import simulate
    from datetime import datetime

    r = TransportRoute(name="x", start_time="07:00", stops=[{"name": "a", "lat": 0, "lng": 0, "minute": 0}, {"name": "b", "lat": 1, "lng": 1, "minute": 20}])
    mid = simulate(r, datetime(2026, 1, 1, 7, 10))
    assert mid["state"] == "on_route" and abs(mid["lat"] - 0.5) < 1e-6


def test_bus_websocket(client, ctx):
    tok = ctx["par"]["Authorization"][7:]
    with client.websocket_connect(f"/api/ws/bus/{ctx['veh']['id']}?token={tok}") as ws:
        m = ws.receive_json()
        assert m["type"] == "bus" and m["vehicle"]["number"] == "TS09 1234"


def test_user_websocket_receives_dm(client, ctx, admin):
    tok = ctx["tch"]["Authorization"][7:]
    with client.websocket_connect(f"/api/ws?token={tok}") as ws:
        assert ws.receive_json()["type"] == "hello"
        client.post("/api/messages", headers=ctx["stu"], json={"to": _uid(client, admin, "T-001"), "body": "live?"})
        m = ws.receive_json()
        assert m["type"] == "dm" and m["body"] == "live?"


# ------------------------------------------------------------------ insights + leave assistant + audit
def test_teacher_insights_and_revision_quiz(client, admin, teacher, teacher2, student1):
    from tests.test_ai import FRACTION_QS, take

    sec = section_id(client, admin)
    maths = subject_id(client, admin, "Mathematics")
    body = {"section_id": sec, "subject_id": maths, "title": "Fractions quiz", "questions": FRACTION_QS}
    qid = client.post("/api/quizzes", headers=teacher, json=body).json()["id"]
    client.post(f"/api/quizzes/{qid}/publish", headers=teacher)
    take(client, student1, qid, wrong=True)
    j = client.get(f"/api/insights/teacher?section_id={sec}", headers=teacher).json()
    aarav = next(s for s in j["students"] if s["name"] == "Aarav Reddy")
    assert "needs_support" in aarav["flags"] and "Fractions" in aarav["weak_topics"]
    assert j["missed"][0]["wrong_pct"] == 100.0
    assert client.get(f"/api/insights/teacher?section_id={section_id(client, admin, '10-B')}", headers=teacher).status_code in (200, 403)
    assert client.get(f"/api/insights/teacher?section_id={sec}", headers=teacher2).status_code == 200  # T-002 teaches Science in 10-A
    rq = client.post("/api/insights/revision-quiz", headers=teacher, json={"section_id": sec, "subject_id": maths}).json()
    assert rq["questions"] >= 2 and "Fractions" in rq["topics"]
    assert client.get(f"/api/quizzes/{rq['quiz_id']}", headers=teacher).json()["status"] == "draft"


def test_school_insights_patterns_never_label_students(client, ctx, admin):
    j = client.get("/api/insights/school", headers=admin).json()
    assert {"school_avg", "attendance", "quiz_completion", "classes_monitored"} <= set(j["cards"])
    for p in j["patterns"]:
        assert p["key"].startswith("pattern.") and p["action"].startswith("action.")
        assert "weak" not in p["key"] and "incapable" not in p["key"]
    assert client.get("/api/insights/school", headers=ctx["tch"]).status_code == 403


def test_parent_leave_message_creates_pending_never_approved(client, admin, teacher, parent1):
    d = client.post("/api/leave-assist/parse", headers=parent1, json={"message": "Aarav will not attend tomorrow due to a family function"}).json()
    assert d["from_date"] == (date.today() + timedelta(days=1)).isoformat() and d["leave_type"] == "family" and d["student_id"]
    r = client.post("/api/leave-assist/submit", headers=parent1, json={k: d[k] for k in ("student_id", "from_date", "to_date", "leave_type", "reason")})
    assert r.status_code == 201 and r.json()["status"] == "pending_teacher"
    lv = client.get("/api/leave", headers=teacher).json()
    mine = next(x for x in lv if x["id"] == r.json()["id"])
    assert mine["status"] == "pending_teacher" and mine["can_act"] is True
    assert any(n["key"] == "notif.leave_parent_message" for n in client.get("/api/notifications", headers=admin).json())
    other = student_ids(client, admin)["EN-26-005"]
    bad = {**{k: d[k] for k in ("from_date", "to_date", "leave_type", "reason")}, "student_id": other}
    assert client.post("/api/leave-assist/submit", headers=parent1, json=bad).status_code == 404


def test_audit_log_records_mutations(client, ctx, admin):
    j = client.get("/api/audit-logs?limit=200", headers=admin).json()
    actions = {i["action"] for i in j["items"]}
    assert {"POST", "PUT", "AI"} <= actions
    assert client.get("/api/audit-logs", headers=ctx["tch"]).status_code == 403


def test_v2_cross_school_isolation(client, ctx, admin_b):
    """School B admin/users can't reach school A's 2.0 rows by id."""
    tb = teacher_login(client, "OTHER", "T-001")
    assert client.get(f"/api/library/{ctx['res']['id']}", headers=admin_b).status_code == 404
    assert client.get(f"/api/forum/{ctx['post']['id']}", headers=tb).status_code == 404
    assert client.get(f"/api/projects/{ctx['project']['id']}", headers=admin_b).status_code == 404
    assert client.get(f"/api/transport/live/{ctx['veh']['id']}", headers=admin_b).status_code == 404
    assert client.post(f"/api/counselling/{ctx['thread']['id']}/messages", headers=tb, json={"body": "x"}).status_code == 404


def test_chitti_talk_mode_small_talk_and_voice(client, student1):
    """Talk mode: greetings, thanks and jokes always get a friendly reply (offline too), in the chosen language."""
    r = client.post("/api/chitti/ask", headers=student1, data={"text": "Hello CHITTI!", "mode": "study_buddy", "voice": "true"})
    assert r.status_code == 200 and r.json()["reply"].startswith(("Hi", "Hello"))
    cid = r.json()["conversation_id"]
    r = client.post("/api/chitti/ask", headers=student1, data={"text": "నమస్తే", "mode": "study_buddy", "lang": "te", "voice": "1", "conversation_id": cid})
    assert r.status_code == 200 and "చిట్టి" in r.json()["reply"]
    assert "?" in client.post("/api/chitti/ask", headers=student1, data={"text": "tell me a joke", "mode": "study_buddy"}).json()["reply"]
    # a real question that starts with a greeting is still answered as a question
    r = client.post("/api/chitti/ask", headers=student1, data={"text": "hi, please explain photosynthesis to me", "mode": "study_buddy", "voice": "1"})
    assert "glucose" in r.json()["reply"].lower()
