"""Phase 3: quizzes (manual + PDF draft), auto-grading, exams (mock/main), marks, publish, report card."""
from datetime import date, datetime, timedelta, timezone

from app.models import QuizAttempt
from tests.conftest import png_bytes, section_id, student_ids, student_login, subject_id

TODAY = date.today().isoformat()


def make_pdf(lines: list[str]) -> bytes:
    """Smallest valid single-page PDF with a text layer (one line per entry)."""
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")  # noqa: E731
    body = "BT /F1 12 Tf 14 TL 50 750 Td " + " ".join(f"({esc(ln)}) '" for ln in lines) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(body)} >>\nstream\n{body}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def mcq(text="2+2?", answer=1, **kw):
    return {"qtype": "mcq", "text": text, "options": ["3", "4", "5"], "answer": answer, "marks": 2, "topic": "Addition", **kw}


QUESTIONS = [
    mcq(explanation="Two plus two is four"),
    {"qtype": "true_false", "text": "Zero is even", "answer": True, "marks": 1, "topic": "Parity"},
    {"qtype": "fill_blank", "text": "Capital of France is ____", "answer": ["Paris"], "marks": 1, "topic": "Geo"},
    {"qtype": "descriptive", "text": "Explain gravity", "answer": "Attraction between masses", "marks": 4, "topic": "Gravity"},
]


def quiz_body(client, h, questions=None, **extra):
    return {"section_id": section_id(client, h), "subject_id": subject_id(client, h, "Mathematics"), "title": "Unit test 1",
            "questions": QUESTIONS if questions is None else questions, **extra}  # fmt: skip


def new_quiz(client, admin, teacher, publish=True, **extra):
    r = client.post("/api/quizzes", headers=teacher, json=quiz_body(client, admin, **extra))
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    if publish:
        assert client.post(f"/api/quizzes/{qid}/publish", headers=teacher).status_code == 200
    return qid


def answers_for(play, **override):
    """Correct answers for the QUESTIONS fixture, in the order the player returns them."""
    by_type = {"mcq": 1, "true_false": True, "fill_blank": " paris ", "descriptive": "Masses attract each other"}
    return [{"question_id": q["id"], "answer": override.get(q["qtype"], by_type[q["qtype"]])} for q in play["questions"]]


# ------------------------------------------------------------------ authoring + validation
def test_quiz_validation_and_teacher_scope(client, admin, teacher, teacher2, student1):
    sec = section_id(client, admin)
    bad = [
        mcq(options=["only one"]),  # < 2 options
        mcq(answer=7),  # index out of range
        {"qtype": "true_false", "text": "x", "answer": "yes"},
        {"qtype": "fill_blank", "text": "x ____", "answer": [1]},
        {"qtype": "mcq", "text": "", "options": ["a", "b"]},
        {"qtype": "essay", "text": "x"},
    ]
    for q in bad:
        assert client.post("/api/quizzes", headers=teacher, json=quiz_body(client, admin, [q])).status_code == 422, q
    # T-002 teaches Science, not Maths, in 10-A; admin/student cannot author
    assert client.post("/api/quizzes", headers=teacher2, json=quiz_body(client, admin)).status_code == 403
    assert client.post("/api/quizzes", headers=admin, json=quiz_body(client, admin)).status_code == 403
    assert client.post("/api/quizzes", headers=student1, json=quiz_body(client, admin)).status_code == 403
    # a draft may have an incomplete key (AI drafts), but cannot be published until complete
    r = client.post("/api/quizzes", headers=teacher, json=quiz_body(client, admin, [mcq(answer=None)]))
    qid = r.json()["id"]
    p = client.post(f"/api/quizzes/{qid}/publish", headers=teacher)
    assert p.status_code == 422 and "1" in p.json()["detail"]
    empty = client.post("/api/quizzes", headers=teacher, json=quiz_body(client, admin, []))
    assert client.post(f"/api/quizzes/{empty.json()['id']}/publish", headers=teacher).status_code == 422
    assert sec


def test_drafts_hidden_and_answer_key_never_leaks_to_students(client, admin, teacher, student1, parent1):
    qid = new_quiz(client, admin, teacher, publish=False)
    assert client.get("/api/quizzes", headers=student1).json() == []
    assert client.post(f"/api/quizzes/{qid}/attempts", headers=student1).status_code == 404
    client.post(f"/api/quizzes/{qid}/publish", headers=teacher)
    assert [q["id"] for q in client.get("/api/quizzes", headers=student1).json()] == [qid]
    assert client.get(f"/api/quizzes/{qid}", headers=student1).status_code == 403  # staff-only (has the key)
    assert client.get(f"/api/quizzes/{qid}", headers=parent1).status_code == 403
    assert client.get(f"/api/quizzes/{qid}", headers=teacher).json()["questions"][0]["answer"] == 1
    play = client.post(f"/api/quizzes/{qid}/attempts", headers=student1).json()
    for q in play["questions"]:
        assert set(q) == {"id", "qtype", "text", "options", "marks"}  # no answer, explanation or topic
    assert "Two plus two" not in str(play)


# ------------------------------------------------------------------ taking + grading
def test_attempt_autograde_and_manual_grade(client, admin, teacher, student1, parent1):
    qid = new_quiz(client, admin, teacher)
    play = client.post(f"/api/quizzes/{qid}/attempts", headers=student1).json()
    again = client.post(f"/api/quizzes/{qid}/attempts", headers=student1)  # resume, same attempt
    assert again.json()["attempt_id"] == play["attempt_id"]
    aid = play["attempt_id"]
    assert client.get(f"/api/attempts/{aid}", headers=student1).status_code == 409  # key hidden until submitted
    r = client.post(f"/api/attempts/{aid}/submit", headers=student1, json={"answers": answers_for(play)})
    assert r.status_code == 200, r.text
    res = r.json()
    # mcq 2 + tf 1 + fill 1 ("  paris " normalised) = 4 of 8; descriptive 4 marks pending
    assert res["status"] == "submitted" and res["score"] == 4 and res["max_score"] == 8 and res["percentage"] is None
    by = {a["qtype"]: a for a in res["answers"]}
    assert by["mcq"]["is_correct"] and by["mcq"]["explanation"] == "Two plus two is four" and by["mcq"]["correct_answer"] == 1
    assert by["fill_blank"]["is_correct"] and by["descriptive"]["is_correct"] is None
    # cannot retake or resubmit
    assert client.post(f"/api/quizzes/{qid}/attempts", headers=student1).status_code == 409
    assert client.post(f"/api/attempts/{aid}/submit", headers=student1, json={"answers": []}).status_code == 409
    # teacher sees it pending, then grades (cap enforced)
    q = client.get("/api/quizzes", headers=teacher).json()[0]
    assert q["attempt_count"] == 1 and q["pending_grading"] == 1
    gid = by["descriptive"]["answer_id"]
    assert client.patch(f"/api/attempts/answers/{gid}/grade", headers=teacher, json={"marks": 9}).status_code == 422
    assert client.patch(f"/api/attempts/answers/{gid}/grade", headers=student1, json={"marks": 1}).status_code == 403
    g = client.patch(f"/api/attempts/answers/{gid}/grade", headers=teacher, json={"marks": 3, "feedback": "Good"})
    assert g.status_code == 200 and g.json()["status"] == "graded" and g.json()["score"] == 7 and g.json()["percentage"] == 87.5
    # objective answers cannot be overridden by hand
    assert client.patch(f"/api/attempts/answers/{by['mcq']['answer_id']}/grade", headers=teacher, json={"marks": 2}).status_code == 409
    # the student was notified; parent can read the child's result; a quiz with attempts is frozen
    notes = client.get("/api/notifications", headers=student1).json()
    assert {"notif.quiz_published", "notif.quiz_graded"} <= {n["key"] for n in notes}
    assert client.get(f"/api/attempts/{aid}", headers=parent1).json()["score"] == 7
    assert client.put(f"/api/quizzes/{qid}", headers=teacher, json=quiz_body(client, admin)).status_code == 409
    rows = client.get(f"/api/quizzes/{qid}/attempts", headers=teacher).json()
    assert len(rows) == 8 and sum(1 for r in rows if r["attempt"]) == 1


def test_wrong_answers_blank_answers_and_unknown_question(client, admin, teacher, student1):
    qid = new_quiz(client, admin, teacher)
    play = client.post(f"/api/quizzes/{qid}/attempts", headers=student1).json()
    aid = play["attempt_id"]
    bogus = client.post(f"/api/attempts/{aid}/submit", headers=student1, json={"answers": [{"question_id": 99999, "answer": 1}]})
    assert bogus.status_code == 422
    wrong = answers_for(play, mcq=0, true_false=False, fill_blank="Lyon", descriptive="  ")
    res = client.post(f"/api/attempts/{aid}/submit", headers=student1, json={"answers": wrong}).json()
    assert res["score"] == 0 and res["status"] == "graded" and res["percentage"] == 0  # blank descriptive = 0, nothing to grade
    # a bool must not pass for an mcq index (True == 1 in Python)
    qid2 = new_quiz(client, admin, teacher, questions=[mcq()], title="x")
    p2 = client.post(f"/api/quizzes/{qid2}/attempts", headers=student1).json()
    r2 = client.post(f"/api/attempts/{p2['attempt_id']}/submit", headers=student1, json={"answers": [{"question_id": p2["questions"][0]["id"], "answer": True}]})
    assert r2.json()["score"] == 0


def test_time_limit_enforced(client, admin, teacher, student1, Session):
    qid = new_quiz(client, admin, teacher, time_limit_minutes=10)
    play = client.post(f"/api/quizzes/{qid}/attempts", headers=student1).json()
    assert play["deadline"] is not None
    with Session() as db:
        a = db.get(QuizAttempt, play["attempt_id"])
        a.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        db.commit()
    res = client.post(f"/api/attempts/{play['attempt_id']}/submit", headers=student1, json={"answers": answers_for(play)}).json()
    assert res["timed_out"] is True and res["score"] == 0  # late answers are not graded


def test_closed_quiz_and_other_section_student(client, admin, teacher, student1):
    qid = new_quiz(client, admin, teacher)
    other = student_login(client, "EDN01", "EN-26-009", "20052011")  # Ishaan, section 9-A
    assert client.get("/api/quizzes", headers=other).json() == []
    assert client.post(f"/api/quizzes/{qid}/attempts", headers=other).status_code == 404
    assert client.post(f"/api/quizzes/{qid}/close", headers=teacher).status_code == 200
    assert client.post(f"/api/quizzes/{qid}/attempts", headers=student1).status_code == 409


def test_parent_needs_own_child(client, admin, teacher, parent1):
    new_quiz(client, admin, teacher)
    st = student_ids(client, admin)
    assert client.get("/api/quizzes", headers=parent1).status_code == 422
    assert len(client.get(f"/api/quizzes?child_id={st['EN-26-001']}", headers=parent1).json()) == 1
    assert client.get(f"/api/quizzes?child_id={st['EN-26-009']}", headers=parent1).json() == []
    assert client.get(f"/api/quizzes?child_id={st['EN-26-002']}", headers=parent1).status_code == 422


# ------------------------------------------------------------------ PDF -> draft
PDF_LINES = [
    "1. What is 2+2?", "A) 3", "B) 4", "C) 5", "Answer: B", "Explanation: basic addition", "Topic: Addition",
    "2. The sun rises in the west. True or False?", "Answer: False",
    "3. Water boils at ____ degrees Celsius.", "Answer: 100",
    "4. Describe photosynthesis.",
]


def pdf_upload(client, admin, teacher, data, name="paper.pdf", ctype="application/pdf", **extra):
    form = {"section_id": section_id(client, admin), "subject_id": subject_id(client, admin, "Mathematics"), **extra}
    return client.post("/api/quizzes/from-pdf", headers=teacher, data=form, files={"file": (name, data, ctype)})


def test_pdf_to_draft_quiz(client, admin, teacher, student1):
    r = pdf_upload(client, admin, teacher, make_pdf(PDF_LINES), title="From PDF")
    assert r.status_code == 201, r.text
    quiz = r.json()
    assert quiz["status"] == "draft" and quiz["source"] == "pdf" and quiz["title"] == "From PDF"
    qs = quiz["questions"]
    assert [q["qtype"] for q in qs] == ["mcq", "true_false", "fill_blank", "descriptive"]
    assert qs[0]["options"] == ["3", "4", "5"] and qs[0]["answer"] == 1 and qs[0]["topic"] == "Addition"
    assert qs[1]["answer"] is False and qs[2]["answer"] == ["100"]
    # AI drafts are not live until the teacher publishes; students cannot see the draft
    assert client.get("/api/quizzes", headers=student1).json() == []
    # teacher reviews/edits then publishes
    body = quiz_body(client, admin, [{**qs[0], "marks": 5}], title="Reviewed")
    assert client.put(f"/api/quizzes/{quiz['id']}", headers=teacher, json=body).json()["total_marks"] == 5
    assert client.post(f"/api/quizzes/{quiz['id']}/publish", headers=teacher).status_code == 200


def test_pdf_rejections(client, admin, teacher, teacher2):
    assert pdf_upload(client, admin, teacher, b"<html><script>x</script></html>", "x.pdf").status_code == 415  # sniffed, not trusted
    assert pdf_upload(client, admin, teacher, png_bytes(), "x.pdf").status_code == 415
    assert pdf_upload(client, admin, teacher, make_pdf(["Just some prose, nothing numbered."])).status_code == 422
    assert pdf_upload(client, admin, teacher2, make_pdf(PDF_LINES)).status_code == 403  # not assigned Maths in 10-A


def test_llm_provider_unconfigured_is_501(client, admin, teacher, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "someday-gpt")
    assert pdf_upload(client, admin, teacher, make_pdf(PDF_LINES)).status_code == 501


def test_stub_generator_unit():
    from app.llm import StubGenerator

    out = StubGenerator().generate("\n".join(PDF_LINES))
    assert len(out) == 4 and out[0].answer == 1 and out[3].qtype == "descriptive"
    assert StubGenerator().generate("no questions here") == []
    assert len(StubGenerator().generate("\n".join(PDF_LINES), max_questions=2)) == 2


# ------------------------------------------------------------------ exams
def exam_body(client, admin, **kw):
    return {"name": "Unit Test 1", "kind": "main", "section_id": section_id(client, admin), "subject_id": subject_id(client, admin, "Mathematics"),
            "exam_date": TODAY, "max_marks": 50, "pass_marks": 20, **kw}  # fmt: skip


def fill_marks(client, teacher, eid, scores: dict[str, float | None], absent=()):
    st = student_ids(client, teacher)
    rows = [{"student_id": st[a], "marks": m} for a, m in scores.items()] + [{"student_id": st[a], "absent": True} for a in absent]
    return client.put(f"/api/exams/{eid}/marks", headers=teacher, json={"rows": rows})


def full_class(top=40.0):
    adm = [f"EN-26-00{i}" for i in range(1, 9)]
    return {a: top - i for i, a in enumerate(adm[:-1])}, [adm[-1]]  # last student absent


def test_exam_flow_marks_publish_visibility(client, admin, teacher, teacher2, student1, parent1):
    r = client.post("/api/exams", headers=teacher, json=exam_body(client, admin))
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    assert r.json()["kind"] == "main" and r.json()["total_students"] == 8
    # who may create / validation
    assert client.post("/api/exams", headers=teacher2, json=exam_body(client, admin)).status_code == 403
    assert client.post("/api/exams", headers=admin, json=exam_body(client, admin)).status_code == 403
    assert client.post("/api/exams", headers=teacher, json=exam_body(client, admin, kind="final")).status_code == 422
    assert client.post("/api/exams", headers=teacher, json=exam_body(client, admin, pass_marks=99)).status_code == 422
    # marks validation
    st = student_ids(client, teacher)
    assert client.put(f"/api/exams/{eid}/marks", headers=teacher, json={"rows": [{"student_id": st["EN-26-001"], "marks": 51}]}).status_code == 422
    assert client.put(f"/api/exams/{eid}/marks", headers=teacher, json={"rows": [{"student_id": st["EN-26-009"], "marks": 5}]}).status_code == 422  # other section
    assert client.put(f"/api/exams/{eid}/marks", headers=teacher, json={"rows": [{"student_id": st["EN-26-001"], "marks": -1}]}).status_code == 422
    assert client.put(f"/api/exams/{eid}/marks", headers=teacher2, json={"rows": []}).status_code == 403
    # partial entry blocks publishing
    assert fill_marks(client, teacher, eid, {"EN-26-001": 45}).status_code == 200
    assert client.post(f"/api/exams/{eid}/publish", headers=teacher).status_code == 409
    scores, absent = full_class()
    sheet = fill_marks(client, teacher, eid, scores, absent).json()
    assert sheet["stats"]["entered"] == 8 and sheet["stats"]["absent"] == 1 and sheet["stats"]["highest"] == 40
    assert sheet["stats"]["passed"] == 7 and sheet["stats"]["failed"] == 0
    # before publish: student/parent see the exam but NOT marks
    ex = client.get("/api/exams", headers=student1).json()[0]
    assert ex["id"] == eid and ex["my_result"] is None and ex["entered_count"] is None
    assert client.get(f"/api/exams/{eid}/marks", headers=student1).status_code == 403
    # publish (teacher or admin), notify, then visible
    assert client.post(f"/api/exams/{eid}/publish", headers=student1).status_code == 403
    assert client.post(f"/api/exams/{eid}/publish", headers=teacher).json()["status"] == "published"
    mine = client.get("/api/exams", headers=student1).json()[0]["my_result"]
    assert mine["marks"] == 40 and mine["percentage"] == 80 and mine["passed"] is True
    st_ids = student_ids(client, admin)
    kid = client.get(f"/api/exams?child_id={st_ids['EN-26-001']}", headers=parent1).json()[0]["my_result"]
    assert kid["marks"] == 40
    assert "notif.results_published" in {n["key"] for n in client.get("/api/notifications", headers=student1).json()}
    assert "notif.results_published" in {n["key"] for n in client.get("/api/notifications", headers=parent1).json()}
    # published results are frozen until unpublished
    assert fill_marks(client, teacher, eid, {"EN-26-001": 10}).status_code == 409
    assert client.patch(f"/api/exams/{eid}", headers=teacher, json={"max_marks": 60}).status_code == 409
    assert client.post(f"/api/exams/{eid}/unpublish", headers=admin).json()["status"] == "draft"
    assert client.get("/api/exams", headers=student1).json()[0]["my_result"] is None
    assert fill_marks(client, teacher, eid, {"EN-26-001": 10}).status_code == 200


def test_exam_paper_and_key_access(client, admin, teacher, student1, parent1):
    eid = client.post("/api/exams", headers=teacher, json=exam_body(client, admin, kind="mock")).json()["id"]
    pdf = make_pdf(["Paper"])
    up = lambda kind, data=pdf, name="p.pdf": client.post(f"/api/exams/{eid}/papers", headers=teacher, data={"kind": kind}, files={"file": (name, data, "application/pdf")})  # noqa: E731
    assert up("paper").json()["has_paper"] and up("key").json()["has_key"]
    assert up("paper", b"<script>alert(1)</script>").status_code == 415
    assert up("other").status_code == 422
    assert client.get(f"/api/exams/{eid}/papers/paper", headers=student1).content == pdf
    assert client.get(f"/api/exams/{eid}/papers/key", headers=student1).status_code == 403
    assert client.get(f"/api/exams/{eid}/papers/key", headers=parent1).status_code == 403
    assert client.get(f"/api/exams/{eid}/papers/key", headers=teacher).content == pdf
    assert client.get(f"/api/exams/{eid}/papers/key", headers=admin).status_code == 200
    ex = client.get(f"/api/exams/{eid}", headers=student1).json()
    assert ex["has_paper"] and not ex["has_key"]  # key existence is not even hinted to students


def test_exam_delete_and_edit_rules(client, admin, teacher, teacher2):
    eid = client.post("/api/exams", headers=teacher, json=exam_body(client, admin)).json()["id"]
    fill_marks(client, teacher, eid, {"EN-26-001": 45})
    assert client.patch(f"/api/exams/{eid}", headers=teacher, json={"max_marks": 40}).status_code == 422  # a mark exceeds new max
    assert client.patch(f"/api/exams/{eid}", headers=teacher, json={"name": "Renamed", "max_marks": 60}).json()["name"] == "Renamed"
    assert client.delete(f"/api/exams/{eid}", headers=teacher2).status_code == 403
    assert client.delete(f"/api/exams/{eid}", headers=teacher).status_code == 204
    assert client.get(f"/api/exams/{eid}", headers=admin).status_code == 404


# ------------------------------------------------------------------ report card
def test_report_card_and_progress(client, admin, teacher, student1, parent1, teacher2):
    maths = subject_id(client, admin, "Mathematics")
    main = client.post("/api/exams", headers=teacher, json=exam_body(client, admin, name="Term 1", exam_date="2026-08-01")).json()["id"]
    mock = client.post("/api/exams", headers=teacher, json=exam_body(client, admin, name="Mock 1", kind="mock", exam_date="2026-07-01", max_marks=20, pass_marks=8)).json()["id"]
    draft = client.post("/api/exams", headers=teacher, json=exam_body(client, admin, name="Unpublished", exam_date="2026-09-01")).json()["id"]
    scores, absent = full_class()
    fill_marks(client, teacher, main, scores, absent)
    fill_marks(client, teacher, mock, {a: 10 for a in scores}, absent)
    fill_marks(client, teacher, draft, {a: 1 for a in scores}, absent)
    client.post(f"/api/exams/{main}/publish", headers=teacher)
    client.post(f"/api/exams/{mock}/publish", headers=teacher)
    # a graded quiz adds a quiz point
    qid = new_quiz(client, admin, teacher, questions=[mcq()])
    play = client.post(f"/api/quizzes/{qid}/attempts", headers=student1).json()
    client.post(f"/api/attempts/{play['attempt_id']}/submit", headers=student1, json={"answers": answers_for(play)})

    rc = client.get("/api/report-card", headers=student1).json()
    assert rc["student_name"] == "Aarav Reddy" and rc["class_name"] == "10" and rc["section_name"] == "A"
    (math,) = rc["subjects"]
    assert math["subject_id"] == maths and math["main_percentage"] == 80 and math["mock_percentage"] == 50 and math["quiz_percentage"] == 100
    assert math["grade"] == "A" and rc["overall_percentage"] == 80 and rc["overall_grade"] == "A"  # mock/quiz do not move the grade
    dates = [p["date"] for p in rc["progress"]]
    assert dates == sorted(dates) and sorted(p["kind"] for p in rc["progress"]) == ["main", "mock", "quiz"]  # graph is date-ordered
    assert [p["kind"] for p in rc["progress"] if p["kind"] != "quiz"] == ["mock", "main"]
    assert "Unpublished" not in str(rc)  # unpublished marks never leak
    assert rc["topics"][0]["topic"] == "Addition" and rc["topics"][0]["percentage"] == 100 and not rc["topics"][0]["weak"]
    # absent student: listed, never averaged
    st = student_ids(client, admin)
    last = student_login(client, "EDN01", "EN-26-008", "02042010")
    rc8 = client.get("/api/report-card", headers=last).json()
    assert rc8["overall_percentage"] is None and rc8["subjects"][0]["exams"][0]["absent"] is True
    # access: parent own child only; teacher of the section; other teacher/section; admin
    assert client.get(f"/api/report-card?student_id={st['EN-26-001']}", headers=parent1).json()["overall_percentage"] == 80
    assert client.get(f"/api/report-card?student_id={st['EN-26-002']}", headers=parent1).status_code == 403
    assert client.get(f"/api/report-card?student_id={st['EN-26-001']}", headers=teacher).status_code == 200
    assert client.get(f"/api/report-card?student_id={st['EN-26-001']}", headers=admin).status_code == 200
    assert client.get(f"/api/report-card?student_id={st['EN-26-002']}", headers=student1).status_code == 403  # a classmate
    assert client.get("/api/report-card", headers=admin).status_code == 422
    assert client.get(f"/api/report-card?student_id={st['EN-26-009']}", headers=teacher2).status_code == 403  # 9-A: T-002 has no class there


def test_student_cannot_read_a_classmates_report_card(client, admin, student1):
    st = student_ids(client, admin)
    # a student may only ever see their own card, whatever student_id they pass
    r = client.get(f"/api/report-card?student_id={st['EN-26-002']}", headers=student1)
    assert r.status_code == 403
