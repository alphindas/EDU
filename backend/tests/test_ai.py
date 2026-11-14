"""Phase 4: robo assistant, practice, mastery, weekly plan, flashcards (SM-2), AI chat + retrieval, limits, isolation."""
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app import learn, models as m, rag
from app.ai import HashEmbedder, StubTutor, cosine
from app.config import get_settings
from tests.conftest import parent_login, png_bytes, section_id, student_login, subject_id

NOTES = (
    "Photosynthesis is the process by which green plants make food using sunlight, water and carbon dioxide.\n\n"
    "Chlorophyll is the green pigment in leaves that absorbs sunlight.\n\n"
    "The mitochondria are the organelles that release energy for the cell."
)


def frac(text, answer, topic="Fractions", **kw):
    return {"qtype": "mcq", "text": text, "options": ["1/2", "1/3", "2/3"], "answer": answer, "marks": 1, "topic": topic,
            "explanation": kw.pop("explanation", "Simplify the fraction first."), **kw}  # fmt: skip


FRACTION_QS = [frac("Half of 1?", 0), frac("A third plus a third?", 2), frac("One over three?", 1, difficulty="easy"),
               {"qtype": "fill_blank", "text": "Half of 8 is ____", "answer": ["4"], "marks": 1, "topic": "Fractions"},
               {"qtype": "mcq", "text": "2+2?", "options": ["3", "4"], "answer": 1, "marks": 1, "topic": "Addition"}]  # fmt: skip


CORRECT = {"Half of 1?": 0, "A third plus a third?": 2, "One over three?": 1}


def take(client, stu, qid, wrong=True):
    """Submit an attempt. wrong=True answers every Fractions question wrongly and Addition correctly. -> result json."""
    play = client.post(f"/api/quizzes/{qid}/attempts", headers=stu).json()
    ans = []
    for q in play["questions"]:
        if q["qtype"] == "fill_blank":
            a = "nope" if wrong else "4"
        elif q["text"] == "2+2?":
            a = 1
        else:
            a = (CORRECT[q["text"]] + 1) % 3 if wrong else CORRECT[q["text"]]
        ans.append({"question_id": q["id"], "answer": a})
    r = client.post(f"/api/attempts/{play['attempt_id']}/submit", headers=stu, json={"answers": ans})
    assert r.status_code == 200, r.text
    return r.json()


def wrong_answers(result):
    return [a for a in result["answers"] if a["is_correct"] is False]


@pytest.fixture()
def quiz_wrong(client, admin, teacher, student1):
    """Published fractions quiz that student1 has submitted with every fractions question wrong."""
    body = {"section_id": section_id(client, admin), "subject_id": subject_id(client, admin, "Mathematics"), "title": "Fractions", "questions": FRACTION_QS}
    qid = client.post("/api/quizzes", headers=teacher, json=body).json()["id"]
    assert client.post(f"/api/quizzes/{qid}/publish", headers=teacher).status_code == 200
    return qid, take(client, student1, qid)


@pytest.fixture()
def student2(client):  # Diya Sharma, 10-A, parent 9000000002
    return student_login(client, "EDN01", "EN-26-002", "22032010")


# ------------------------------------------------------------------ pure logic
def test_hash_embedder_is_deterministic_and_ranks_related_text_higher():
    e = HashEmbedder()
    a, b, c = e.embed(["photosynthesis in green plants", "how plants do photosynthesis", "the french revolution began in 1789"])
    assert e.embed(["photosynthesis in green plants"])[0] == a
    assert cosine(a, b) > cosine(a, c)
    assert abs(cosine(a, a) - 1) < 1e-3


def test_sm2_schedule():
    ease, iv, reps, lapsed = learn.sm2(2.5, 0, 0, 4)
    assert (iv, reps, lapsed) == (1, 1, False)
    ease, iv, reps, _ = learn.sm2(ease, iv, reps, 4)
    assert (iv, reps) == (6, 2)
    ease, iv, reps, _ = learn.sm2(ease, iv, reps, 5)
    assert (iv, reps) == (15, 3)  # 6 days * ease 2.5
    e2, iv2, reps2, lapsed = learn.sm2(ease, iv, reps, 1)  # forgot: back to tomorrow
    assert (iv2, reps2, lapsed) == (1, 0, True)
    assert learn.sm2(1.3, 1, 1, 3)[0] >= 1.3  # ease never drops below 1.3


def test_plan_rules():
    w = [m.TopicMastery(subject_id=1, topic="Fractions", mastery=20.0), m.TopicMastery(subject_id=1, topic="Algebra", mastery=45.0)]
    items = learn.build_plan_items(w, due_cards=3, has_any_mastery=True)
    rev = {i["topic"]: i for i in items if i["kind"] == "revise"}
    prac = {i["topic"]: i for i in items if i["kind"] == "practice"}
    assert prac["Fractions"]["day"] - rev["Fractions"]["day"] == 2  # spaced two days later
    assert rev["Fractions"]["difficulty"] == "easy" and rev["Algebra"]["difficulty"] == "medium"  # very weak -> easier work
    assert {i["day"] for i in items if i["kind"] == "flashcards"} == {1, 3, 5}
    assert items[-1]["kind"] == "rest" and items[-1]["day"] == 6
    assert [i["id"] for i in items] == list(range(1, len(items) + 1))
    assert learn.build_plan_items([], 0, False)[0]["kind"] == "start"
    assert learn.build_plan_items([], 0, True)[0]["kind"] == "maintain"


def test_chunking_keeps_text_and_size():
    chunks = rag.chunk_text(NOTES * 5, 200)
    assert all(len(c) <= 200 for c in chunks) and len(chunks) > 3
    assert rag.chunk_text("") == []


def test_stub_tutor_flashcards_from_definitions():
    cards = StubTutor().make_cards(NOTES)
    fronts = [c.front for c in cards]
    assert fronts == ["What is Photosynthesis?", "What is Chlorophyll?", "What are mitochondria?"]  # leading article dropped


# ------------------------------------------------------------------ robo assistant
def test_robo_modes_cache_and_access(client, quiz_wrong, student1, student2, teacher, parent1, Session):
    qid, res = quiz_wrong
    wrong = wrong_answers(res)
    assert len(wrong) == 4
    aid = next(a["answer_id"] for a in wrong if a["text"] == "Half of 1?")
    r = client.post("/api/ai/robo", headers=student1, json={"answer_id": aid, "mode": "explain"})
    assert r.status_code == 200
    j = r.json()
    assert "1/2" in j["text"] and "Simplify the fraction first." in j["text"] and j["provider"] == "stub" and j["cached"] is False
    w = client.post("/api/ai/robo", headers=student1, json={"answer_id": aid, "mode": "why_wrong"}).json()
    assert "You answered: 1/3" in w["text"] and "The correct answer is: 1/2" in w["text"]
    # same request again is served from the cache and is not charged
    with Session() as db:
        calls = db.scalar(select(func.count()).select_from(m.AiCall))
    again = client.post("/api/ai/robo", headers=student1, json={"answer_id": aid, "mode": "explain"}).json()
    assert again["cached"] is True and again["text"] == j["text"]
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(m.AiCall)) == calls
    # only wrong answers; only the owner; only students
    right = next(a["answer_id"] for a in res["answers"] if a["is_correct"])
    assert client.post("/api/ai/robo", headers=student1, json={"answer_id": right, "mode": "explain"}).status_code == 409
    assert client.post("/api/ai/robo", headers=student2, json={"answer_id": aid, "mode": "explain"}).status_code == 403
    for h in (teacher, parent1):
        assert client.post("/api/ai/robo", headers=h, json={"answer_id": aid, "mode": "explain"}).status_code == 403
    assert client.post("/api/ai/robo", headers=student1, json={"answer_id": aid, "mode": "bogus"}).status_code == 422
    assert client.post("/api/ai/robo", headers=student1, json={"answer_id": 99999, "mode": "explain"}).status_code == 404


def test_robo_next_picks_same_topic_without_leaking_key_and_check_grades(client, quiz_wrong, student1):
    qid, res = quiz_wrong
    first = next(a for a in wrong_answers(res) if a["text"] == "Half of 1?")
    n = client.post("/api/ai/robo", headers=student1, json={"answer_id": first["answer_id"], "mode": "next"}).json()
    p = n["practice"]
    assert p["topic"] == "Fractions" and p["question_id"] != first["question_id"]
    assert set(p) == {"question_id", "qtype", "text", "options", "topic", "marks"}  # no answer / explanation
    assert p["qtype"] != "descriptive"
    seen = [p["question_id"]]
    for _ in range(5):  # walk through the pool using exclude; it ends with practice=None and a fallback sentence
        n = client.post("/api/ai/robo", headers=student1, json={"answer_id": first["answer_id"], "mode": "next", "exclude": seen}).json()
        if n["practice"] is None:
            assert "no other question" in n["text"].lower()
            break
        assert n["practice"]["question_id"] not in seen
        seen.append(n["practice"]["question_id"])
    else:
        pytest.fail("pool never ran out")
    assert len(seen) == 3  # 3 other Fractions questions (all non-descriptive)
    # check endpoint: right and wrong, key only returned here
    qs = {a["question_id"]: a for a in res["answers"]}
    mcq_id = next(i for i in seen if qs[i]["qtype"] == "mcq")
    right_idx = qs[mcq_id]["correct_answer"]
    ok = client.post(f"/api/ai/practice/{mcq_id}/check", headers=student1, json={"answer": right_idx}).json()
    bad = client.post(f"/api/ai/practice/{mcq_id}/check", headers=student1, json={"answer": (right_idx + 1) % 3}).json()
    assert ok["is_correct"] is True and bad["is_correct"] is False and bad["correct_answer"] == right_idx
    # topic practice list
    lst = client.get("/api/ai/practice?topic=Fractions&limit=2", headers=student1).json()
    assert len(lst) == 2 and all("answer" not in x for x in lst)
    assert client.get("/api/ai/practice?topic=Nothing", headers=student1).json() == []


def test_practice_check_refuses_questions_from_quizzes_not_yet_submitted(client, admin, teacher, student1, student2, quiz_wrong):
    body = {"section_id": section_id(client, admin), "subject_id": subject_id(client, admin, "Mathematics"), "title": "Unseen",
            "questions": [frac("Secret Q?", 0, topic="Fractions")]}  # fmt: skip
    q3 = client.post("/api/quizzes", headers=teacher, json=body).json()
    client.post(f"/api/quizzes/{q3['id']}/publish", headers=teacher)
    unseen = client.get(f"/api/quizzes/{q3['id']}", headers=teacher).json()["questions"][0]["id"]
    assert client.post(f"/api/ai/practice/{unseen}/check", headers=student1, json={"answer": 0}).status_code == 404
    assert "Secret Q?" not in str(client.get("/api/ai/practice?topic=Fractions&limit=20", headers=student1).json())
    # and student2 never submitted the fractions quiz either, so they get nothing from it
    qid, res = quiz_wrong
    some = res["answers"][0]["question_id"]
    assert client.post(f"/api/ai/practice/{some}/check", headers=student2, json={"answer": 0}).status_code == 404
    assert client.get("/api/ai/practice?topic=Fractions", headers=student2).json() == []


# ------------------------------------------------------------------ mastery + plan
def test_mastery_weak_topics_and_visibility(client, quiz_wrong, student1, student2, parent1, teacher, admin):
    r = client.get("/api/ai/mastery", headers=student1).json()
    by = {t["topic"]: t for t in r["topics"]}
    assert by["Fractions"]["mastery"] == 0 and by["Fractions"]["level"] == "weak" and by["Fractions"]["total"] == 4
    assert by["Addition"]["level"] == "strong"
    assert r["weak_count"] == 1 and r["topics"][0]["topic"] == "Fractions"  # weakest first
    sid1 = r["student_id"]
    assert client.get(f"/api/ai/mastery?student_id={sid1}", headers=parent1).json()["weak_count"] == 1
    assert client.get(f"/api/ai/mastery?student_id={sid1}", headers=teacher).status_code == 200
    assert client.get(f"/api/ai/mastery?student_id={sid1}", headers=admin).status_code == 200
    assert client.get(f"/api/ai/mastery?student_id={sid1}", headers=student2).status_code == 403  # classmate
    ph2, _ = parent_login(client, "EDN01", "9000000002")
    assert client.get(f"/api/ai/mastery?student_id={sid1}", headers=ph2).status_code == 403  # someone else's child
    assert client.get("/api/ai/mastery", headers=parent1).status_code == 422  # parents must name a child
    assert client.get("/api/ai/mastery", headers=student2).json()["topics"] == []  # no data yet


def test_weekly_plan_lifecycle(client, quiz_wrong, student1, student2, parent1, teacher, admin):
    p = client.get("/api/ai/plan", headers=student1).json()
    assert p["week_start"] == learn.week_start(date.today()).isoformat() and p["stale"] is False
    kinds = [(i["kind"], i["topic"]) for i in p["items"]]
    assert ("revise", "Fractions") in kinds and ("practice", "Fractions") in kinds and kinds[-1][0] == "rest"
    assert next(i for i in p["items"] if i["kind"] == "revise")["subject"] == "Mathematics"
    assert client.get("/api/ai/plan", headers=student1).json()["id"] == p["id"]  # stable within the week
    item = next(i for i in p["items"] if i["kind"] == "revise")
    t = client.patch(f"/api/ai/plan/{p['id']}/items/{item['id']}", headers=student1, json={"done": True}).json()
    assert next(i for i in t["items"] if i["id"] == item["id"])["done"] is True
    # classmate, parent, teacher can't tick; parent/teacher can read
    assert client.patch(f"/api/ai/plan/{p['id']}/items/{item['id']}", headers=student2, json={"done": False}).status_code == 404
    assert client.patch(f"/api/ai/plan/{p['id']}/items/{item['id']}", headers=parent1, json={"done": False}).status_code == 403
    assert client.patch(f"/api/ai/plan/{p['id']}/items/999", headers=student1, json={"done": True}).status_code == 404
    sid1 = p["student_id"]
    assert client.get(f"/api/ai/plan?student_id={sid1}", headers=parent1).status_code == 200
    assert client.get(f"/api/ai/plan?student_id={sid1}", headers=teacher).status_code == 200
    assert client.get(f"/api/ai/plan?student_id={sid1}", headers=student2).status_code == 403
    # regenerate keeps ticks; new cards due add flashcard slots
    client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "mistakes"})
    g = client.post("/api/ai/plan/regenerate", headers=student1).json()
    assert next(i for i in g["items"] if i["kind"] == "revise")["done"] is True
    assert g["due_cards"] > 0 and any(i["kind"] == "flashcards" for i in g["items"])
    # student with no data gets a "start" plan
    assert client.get("/api/ai/plan", headers=student2).json()["items"][0]["kind"] == "start"


def test_plan_goes_stale_when_weak_topics_change(client, quiz_wrong, admin, teacher, student1):
    p = client.get("/api/ai/plan", headers=student1).json()
    assert p["stale"] is False
    body = {"section_id": section_id(client, admin), "subject_id": subject_id(client, admin, "Mathematics"), "title": "Algebra",
            "questions": [{"qtype": "mcq", "text": "x+1=2, x?", "options": ["0", "1"], "answer": 1, "marks": 1, "topic": "Algebra"}]}  # fmt: skip
    q = client.post("/api/quizzes", headers=teacher, json=body).json()["id"]
    client.post(f"/api/quizzes/{q}/publish", headers=teacher)
    play = client.post(f"/api/quizzes/{q}/attempts", headers=student1).json()
    client.post(f"/api/attempts/{play['attempt_id']}/submit", headers=student1, json={"answers": [{"question_id": play["questions"][0]["id"], "answer": 0}]})
    assert client.get("/api/ai/plan", headers=student1).json()["stale"] is True  # Algebra is now weak too
    fresh = client.post("/api/ai/plan/regenerate", headers=student1).json()
    assert fresh["stale"] is False and {i["topic"] for i in fresh["items"] if i["kind"] == "revise"} == {"Fractions", "Algebra"}


def test_gap_report(client, quiz_wrong, student1, student2, teacher, teacher2, admin, parent1):
    sec = section_id(client, admin)
    qid, _ = quiz_wrong
    take(client, student2, qid, wrong=False)  # classmate does fine
    g = client.get(f"/api/ai/gap-report?section_id={sec}", headers=teacher).json()
    top = g["topics"][0]
    assert top["topic"] == "Fractions" and top["students_attempted"] == 2 and top["weak_students"] == 1
    assert top["weak_list"][0]["name"] == "Aarav Reddy" and top["avg_mastery"] == 50.0
    assert client.get(f"/api/ai/gap-report?section_id={sec}", headers=admin).status_code == 200
    # T-002 teaches Science in 10-A (not Maths): sees no Maths topics
    assert client.get(f"/api/ai/gap-report?section_id={sec}", headers=teacher2).json()["topics"] == []
    for h in (student1, parent1):
        assert client.get(f"/api/ai/gap-report?section_id={sec}", headers=h).status_code == 403
    assert client.get("/api/ai/gap-report?section_id=99999", headers=teacher).status_code == 404


# ------------------------------------------------------------------ flashcards
def test_flashcards_from_mistakes_review_and_stats(client, quiz_wrong, student1, student2, parent1, teacher):
    g = client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "mistakes"}).json()
    assert g["created"] == 4 and g["skipped_duplicates"] == 0
    card = next(c for c in g["cards"] if c["front"] == "Half of 1?")
    assert card["source"] == "mistakes" and card["topic"] == "Fractions" and card["due_date"] == date.today().isoformat()
    assert card["subject_id"] is not None
    again = client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "mistakes"}).json()
    assert again["created"] == 0 and again["skipped_duplicates"] == 4
    assert client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "mistakes", "topic": "Nope"}).json()["created"] == 0
    assert len(client.get("/api/ai/flashcards?due=true", headers=student1).json()) == 4
    # review: good -> tomorrow, then 6 days; forgetting resets
    r1 = client.post(f"/api/ai/flashcards/{card['id']}/review", headers=student1, json={"quality": 4}).json()
    assert r1["interval_days"] == 1 and r1["repetitions"] == 1 and r1["due_date"] == (date.today() + timedelta(days=1)).isoformat()
    r2 = client.post(f"/api/ai/flashcards/{card['id']}/review", headers=student1, json={"quality": 5}).json()
    assert r2["interval_days"] == 6 and r2["ease"] > 2.5
    r3 = client.post(f"/api/ai/flashcards/{card['id']}/review", headers=student1, json={"quality": 0}).json()
    assert r3["interval_days"] == 1 and r3["repetitions"] == 0 and r3["lapses"] == 1
    assert len(client.get("/api/ai/flashcards?due=true", headers=student1).json()) == 3
    st = client.get("/api/ai/flashcards/stats", headers=student1).json()
    assert st["total"] == 4 and st["due"] == 3 and st["new"] == 3
    assert client.post(f"/api/ai/flashcards/{card['id']}/review", headers=student1, json={"quality": 6}).status_code == 422
    # privacy between students / roles
    assert client.post(f"/api/ai/flashcards/{card['id']}/review", headers=student2, json={"quality": 4}).status_code == 404
    assert client.delete(f"/api/ai/flashcards/{card['id']}", headers=student2).status_code == 404
    assert client.get("/api/ai/flashcards", headers=student2).json() == []
    for h in (parent1, teacher):
        assert client.get("/api/ai/flashcards", headers=h).status_code == 403
    assert client.delete(f"/api/ai/flashcards/{card['id']}", headers=student1).status_code == 204


def test_flashcards_manual_and_from_notes(client, student1, admin):
    c = client.post("/api/ai/flashcards", headers=student1, json={"front": "H2O?", "back": "Water", "topic": "Chem"})
    assert c.status_code == 201 and c.json()["source"] == "manual"
    assert client.post("/api/ai/flashcards", headers=student1, json={"front": "x", "back": "y", "subject_id": 99999}).status_code == 404
    doc = client.post("/api/ai/documents", headers=student1, files={"file": ("notes.txt", NOTES.encode(), "text/plain")}).json()
    assert doc["readable"] and doc["chunk_count"] >= 1
    g = client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "notes", "document_id": doc["id"], "topic": "Biology"}).json()
    assert g["created"] == 3 and {c["source"] for c in g["cards"]} == {"notes"} and g["cards"][0]["topic"] == "Biology"
    assert client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "notes"}).status_code == 422
    img = client.post("/api/ai/documents", headers=student1, files={"file": ("p.png", png_bytes(), "image/png")}).json()
    assert img["readable"] is False
    assert client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "notes", "document_id": img["id"]}).status_code == 422


# ------------------------------------------------------------------ AI chat
def new_conv(client, h):
    r = client.post("/api/ai/conversations", headers=h, json={})
    assert r.status_code == 201
    return r.json()["id"]


def say(client, h, cid, text, file=None, lang="en"):
    return client.post(f"/api/ai/conversations/{cid}/messages", headers=h, data={"text": text, "lang": lang}, files={"file": file} if file else None)


def test_chat_retrieval_over_uploaded_notes(client, student1):
    cid = new_conv(client, student1)
    # no notes yet: honest offline answer, no sources
    r = say(client, student1, cid, "What is photosynthesis?").json()
    assert r["assistant_message"]["sources"] == [] and "offline demo mode" in r["assistant_message"]["content"]
    assert r["assistant_message"]["provider"] == "stub"
    # upload notes with the question: answer is grounded in them, with a source
    r = say(client, student1, cid, "What is photosynthesis?", ("bio.txt", NOTES.encode(), "text/plain"))
    assert r.status_code == 201
    j = r.json()
    assert j["document"]["name"] == "bio.txt" and j["user_message"]["attachment_id"] == j["document"]["id"]
    a = j["assistant_message"]
    assert "green plants make food" in a["content"] and a["sources"][0]["name"] == "bio.txt"
    # a later question in the SAME or ANOTHER conversation still retrieves from the notes
    cid2 = new_conv(client, student1)
    a2 = say(client, student1, cid2, "which pigment absorbs sunlight in leaves").json()["assistant_message"]
    assert "Chlorophyll" in a2["content"]
    # unrelated question -> no grounding
    a3 = say(client, student1, cid2, "Who won the 1983 cricket world cup?").json()["assistant_message"]
    assert a3["sources"] == []
    # history persisted in order; title set from first message
    conv = client.get(f"/api/ai/conversations/{cid}", headers=student1).json()
    assert [x["role"] for x in conv["messages"]] == ["user", "assistant"] * 2 and conv["title"] == "What is photosynthesis?"
    assert [c["id"] for c in client.get("/api/ai/conversations", headers=student1).json()][0] == cid2  # most recent first


def test_chat_files_images_validation(client, student1):
    cid = new_conv(client, student1)
    r = say(client, student1, cid, "read this image", ("p.png", png_bytes(), "image/png")).json()
    assert r["document"]["readable"] is False and "could not read" in r["assistant_message"]["content"]
    # client-claimed type is ignored: binary junk named .txt / claimed pdf is rejected; exe-like bytes too
    assert say(client, student1, cid, "x", ("a.pdf", b"\x00\x01\x02\xff\xfe", "application/pdf")).status_code == 415
    assert say(client, student1, cid, "x", ("a.txt", b"MZ\x90\x00\x03\x00", "text/plain")).status_code == 415
    assert say(client, student1, cid, "x", ("a.txt", b"", "text/plain")).status_code == 422
    assert say(client, student1, cid, "   ").status_code == 422
    assert client.post(f"/api/ai/conversations/{cid}/messages", headers=student1, data={"text": "x" * 2001}).status_code == 422
    assert client.post(f"/api/ai/conversations/{cid}/messages", headers=student1, data={"text": "hi", "lang": "fr"}).status_code == 422


def test_chat_access_and_privacy(client, student1, student2, teacher, parent1, admin):
    cid = new_conv(client, student1)
    d = say(client, student1, cid, "q", ("n.txt", NOTES.encode(), "text/plain")).json()["document"]
    # another student in the same school: 404 on conversation, document, file, delete, and no retrieval from their notes
    assert client.get(f"/api/ai/conversations/{cid}", headers=student2).status_code == 404
    assert say(client, student2, cid, "hi").status_code == 404
    assert client.delete(f"/api/ai/conversations/{cid}", headers=student2).status_code == 404
    assert client.get(f"/api/ai/documents/{d['id']}/file", headers=student2).status_code == 404
    assert client.delete(f"/api/ai/documents/{d['id']}", headers=student2).status_code == 404
    assert client.get("/api/ai/documents", headers=student2).json() == [] and client.get("/api/ai/conversations", headers=student2).json() == []
    c2 = new_conv(client, student2)
    a = say(client, student2, c2, "what is photosynthesis").json()["assistant_message"]
    assert a["sources"] == [] and "green plants" not in a["content"]
    # parents/admin have no AI Chat; teachers do (their own, private)
    for h in (parent1, admin):
        assert client.post("/api/ai/conversations", headers=h, json={}).status_code == 403
        assert client.get("/api/ai/documents", headers=h).status_code == 403
    tc = new_conv(client, teacher)
    assert say(client, teacher, tc, "Make a worksheet").status_code == 201
    assert client.get(f"/api/ai/conversations/{tc}", headers=student1).status_code == 404
    # owner can fetch the file (authenticated, nosniff) and delete it: chunks + message link are cleaned
    f = client.get(f"/api/ai/documents/{d['id']}/file", headers=student1)
    assert f.status_code == 200 and f.headers["x-content-type-options"] == "nosniff" and f.content == NOTES.encode()
    assert client.delete(f"/api/ai/documents/{d['id']}", headers=student1).status_code == 204
    assert client.get(f"/api/ai/documents/{d['id']}/file", headers=student1).status_code == 404
    a = say(client, student1, cid, "what is photosynthesis").json()["assistant_message"]
    assert a["sources"] == []  # chunks gone
    assert client.get(f"/api/ai/conversations/{cid}", headers=student1).json()["messages"][0]["attachment_id"] is None
    assert client.delete(f"/api/ai/conversations/{cid}", headers=student1).status_code == 204
    assert client.get(f"/api/ai/conversations/{cid}", headers=student1).status_code == 404


def test_daily_limit_and_logging(client, quiz_wrong, student1, monkeypatch, Session):
    monkeypatch.setattr(get_settings(), "ai_daily_limit", 3)
    cid = new_conv(client, student1)
    assert say(client, student1, cid, "one").status_code == 201
    assert say(client, student1, cid, "two").status_code == 201
    wrong = wrong_answers(quiz_wrong[1])
    assert client.post("/api/ai/robo", headers=student1, json={"answer_id": wrong[0]["answer_id"], "mode": "explain"}).status_code == 200
    r = say(client, student1, cid, "three")
    assert r.status_code == 429
    # limit hit: a refused request stores nothing, a cached robo answer is still free
    assert len(client.get(f"/api/ai/conversations/{cid}", headers=student1).json()["messages"]) == 4
    assert client.post("/api/ai/robo", headers=student1, json={"answer_id": wrong[0]["answer_id"], "mode": "explain"}).json()["cached"] is True
    assert client.post("/api/ai/robo", headers=student1, json={"answer_id": wrong[1]["answer_id"], "mode": "explain"}).status_code == 429
    with Session() as db:
        assert {c.kind for c in db.scalars(select(m.AiCall))} == {"chat", "robo"}


def test_unconfigured_real_provider_is_501(client, quiz_wrong, student1, monkeypatch):
    cid = new_conv(client, student1)
    aid = wrong_answers(quiz_wrong[1])[0]["answer_id"]
    monkeypatch.setattr(get_settings(), "ai_provider", "openai")
    assert say(client, student1, cid, "hello").status_code == 501
    assert client.post("/api/ai/robo", headers=student1, json={"answer_id": aid, "mode": "explain"}).status_code == 501
    assert client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "mistakes"}).status_code == 501


# ------------------------------------------------------------------ tenant isolation (identical logins in both schools)
def populate_ai(client, adm, tch, stu):
    """One row in every Phase 4 table for one school (used by test_tenant_isolation too). Returns ids."""
    body = {"section_id": section_id(client, adm), "subject_id": subject_id(client, adm, "Mathematics"), "title": "Fractions", "questions": FRACTION_QS}
    qid = client.post("/api/quizzes", headers=tch, json=body).json()["id"]
    client.post(f"/api/quizzes/{qid}/publish", headers=tch)
    res = take(client, stu, qid)
    wrong = wrong_answers(res)
    answer_id = wrong[0]["answer_id"]
    assert client.post("/api/ai/robo", headers=stu, json={"answer_id": answer_id, "mode": "explain"}).status_code == 200  # RoboHelp + AiCall
    plan = client.get("/api/ai/plan", headers=stu).json()  # TopicMastery + LearningPlan
    card = client.post("/api/ai/flashcards/generate", headers=stu, json={"source": "mistakes"}).json()["cards"][0]  # Flashcard
    cid = client.post("/api/ai/conversations", headers=stu, json={}).json()["id"]
    turn = client.post(f"/api/ai/conversations/{cid}/messages", headers=stu, data={"text": "what is photosynthesis"},
                       files={"file": ("n.txt", NOTES.encode(), "text/plain")}).json()  # conversation, messages, document, chunks
    return dict(qid=qid, question_id=wrong[0]["question_id"], answer_id=answer_id, plan=plan, card=card, cid=cid, doc=turn["document"]["id"])


def test_phase4_other_school_cannot_touch_ai_rows(client, admin, admin_b, teacher, teacher_b, student1, student1_b):
    a = populate_ai(client, admin, teacher, student1)
    b = populate_ai(client, admin_b, teacher_b, student1_b)
    # A's student (same login ids as B's) pokes at B's ids -> 404 (or 403 where the owner check fires first), never data
    for url in (f"/api/ai/conversations/{b['cid']}",):
        assert client.get(url, headers=student1).status_code == 404
    assert client.post(f"/api/ai/conversations/{b['cid']}/messages", headers=student1, data={"text": "hi"}).status_code == 404
    assert client.delete(f"/api/ai/conversations/{b['cid']}", headers=student1).status_code == 404
    assert client.get(f"/api/ai/documents/{b['doc']}/file", headers=student1).status_code == 404
    assert client.delete(f"/api/ai/documents/{b['doc']}", headers=student1).status_code == 404
    assert client.post("/api/ai/robo", headers=student1, json={"answer_id": b["answer_id"], "mode": "explain"}).status_code == 404
    assert client.post(f"/api/ai/practice/{b['question_id']}/check", headers=student1, json={"answer": 0}).status_code == 404
    assert client.post(f"/api/ai/flashcards/{b['card']['id']}/review", headers=student1, json={"quality": 4}).status_code == 404
    assert client.delete(f"/api/ai/flashcards/{b['card']['id']}", headers=student1).status_code == 404
    assert client.patch(f"/api/ai/plan/{b['plan']['id']}/items/1", headers=student1, json={"done": True}).status_code == 404
    assert client.post("/api/ai/flashcards/generate", headers=student1, json={"source": "notes", "document_id": b["doc"]}).status_code == 404
    assert client.get(f"/api/ai/mastery?student_id={b['plan']['student_id']}", headers=admin).status_code == 404
    assert client.get(f"/api/ai/plan?student_id={b['plan']['student_id']}", headers=admin).status_code == 404
    sec_b = section_id(client, admin_b)
    assert client.get(f"/api/ai/gap-report?section_id={sec_b}", headers=teacher).status_code == 404
    # A's own lists only hold A's rows; B's retrieval never surfaces A's notes
    assert {c["id"] for c in client.get("/api/ai/conversations", headers=student1).json()} == {a["cid"]}
    assert {d["id"] for d in client.get("/api/ai/documents", headers=student1).json()} == {a["doc"]}
    assert {c["id"] for c in client.get("/api/ai/flashcards", headers=student1).json()}.isdisjoint({b["card"]["id"]})
    # B intact
    assert client.get(f"/api/ai/conversations/{b['cid']}", headers=student1_b).status_code == 200
    assert len(client.get("/api/ai/flashcards", headers=student1_b).json()) == 4


# ------------------------------------------------------------------ concurrency (found in the browser: Learning page loads mastery + plan at once)
def test_concurrent_mastery_refresh_does_not_500(client, quiz_wrong, student1, Session, monkeypatch):
    sid = client.get("/api/ai/mastery", headers=student1).json()["student_id"]
    with Session() as db:  # start from a clean slate so both "requests" try to INSERT
        db.query(m.TopicMastery).delete()
        db.commit()
        school = db.scalar(select(m.Student.school_id).where(m.Student.id == sid))
    real = learn._sync_mastery
    calls = {"n": 0}

    def racing(db, school_id, student_id):
        rows = real(db, school_id, student_id)  # this session now holds pending INSERTs...
        calls["n"] += 1
        if calls["n"] == 1:
            with Session() as other:  # ...and another request commits the same rows first
                learn.recompute_mastery(other, school_id, student_id)
        return rows

    monkeypatch.setattr(learn, "_sync_mastery", racing)
    with Session() as db:
        rows = learn.recompute_mastery(db, school, sid)
        assert {r.topic for r in rows} == {"Fractions", "Addition"}
        assert db.scalar(select(func.count()).select_from(m.TopicMastery)) == 2  # no duplicates
    assert calls["n"] >= 3  # racing call, the other request's call, and the retry


def test_concurrent_plan_creation_uses_existing_plan(client, quiz_wrong, student1, Session, monkeypatch):
    first = client.get("/api/ai/plan", headers=student1).json()
    # Simulate: the plan lookup misses once although the row exists (another request inserted it a moment ago).
    from sqlalchemy.orm import Session as SASession

    orig = SASession.scalar
    state = {"missed": False}

    def flaky(self, stmt, *a, **k):
        if "learning_plans" in str(stmt) and not state["missed"]:
            state["missed"] = True
            return None
        return orig(self, stmt, *a, **k)

    monkeypatch.setattr(SASession, "scalar", flaky)
    again = client.get("/api/ai/plan", headers=student1)
    assert again.status_code == 200 and again.json()["id"] == first["id"] and state["missed"]
