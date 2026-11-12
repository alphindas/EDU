"""School A must never read or modify school B's data. Both schools are seeded with IDENTICAL logins
(admin/admin123, T-001, EN-26-001, 9000000001), so any leak would be visible."""
from sqlalchemy import select

from app.models import Parent, Student, Subject, User
from tests.conftest import login, parent_login

LISTS = ["/api/classes", "/api/sections", "/api/subjects", "/api/assignments", "/api/academic-years"]


def test_lists_only_contain_own_school(client, admin, admin_b):
    a_ids, b_ids = {}, {}
    for url in LISTS:
        a = client.get(url, headers=admin).json()
        b = client.get(url, headers=admin_b).json()
        assert a and b
        a_ids[url], b_ids[url] = {x["id"] for x in a}, {x["id"] for x in b}
        assert a_ids[url].isdisjoint(b_ids[url]), f"{url} leaks rows between schools"
    for url in ("/api/students", "/api/teachers", "/api/parents"):
        a = {x["id"] for x in client.get(url, headers=admin).json()["items"]}
        b = {x["id"] for x in client.get(url, headers=admin_b).json()["items"]}
        assert a and b and a.isdisjoint(b), f"{url} leaks rows between schools"


def test_cannot_read_update_delete_other_schools_rows_by_id(client, admin, admin_b):
    b_student = client.get("/api/students", headers=admin_b).json()["items"][0]
    b_teacher = client.get("/api/teachers", headers=admin_b).json()["items"][0]
    b_class = client.get("/api/classes", headers=admin_b).json()[0]
    b_section = client.get("/api/sections", headers=admin_b).json()[0]
    b_subject = client.get("/api/subjects", headers=admin_b).json()[0]
    b_parent = client.get("/api/parents", headers=admin_b).json()["items"][0]
    # A's admin guesses B's ids -> 404, never 200/403-with-data
    assert client.get(f"/api/students/{b_student['id']}", headers=admin).status_code == 404
    assert client.get(f"/api/teachers/{b_teacher['id']}", headers=admin).status_code == 404
    assert client.get(f"/api/parents/{b_parent['id']}", headers=admin).status_code == 404
    assert client.patch(f"/api/students/{b_student['id']}", headers=admin, json={"full_name": "pwned"}).status_code == 404
    assert client.patch(f"/api/teachers/{b_teacher['id']}", headers=admin, json={"full_name": "pwned"}).status_code == 404
    assert client.patch(f"/api/classes/{b_class['id']}", headers=admin, json={"name": "pwned"}).status_code == 404
    assert client.patch(f"/api/sections/{b_section['id']}", headers=admin, json={"name": "Z"}).status_code == 404
    assert client.patch(f"/api/subjects/{b_subject['id']}", headers=admin, json={"name": "pwned"}).status_code == 404
    assert client.delete(f"/api/students/{b_student['id']}", headers=admin).status_code == 404
    assert client.delete(f"/api/teachers/{b_teacher['id']}", headers=admin).status_code == 404
    assert client.delete(f"/api/classes/{b_class['id']}", headers=admin).status_code == 404
    assert client.delete(f"/api/sections/{b_section['id']}", headers=admin).status_code == 404
    assert client.delete(f"/api/subjects/{b_subject['id']}", headers=admin).status_code == 404
    # B's data is untouched
    assert client.get(f"/api/students/{b_student['id']}", headers=admin_b).json()["full_name"] == b_student["full_name"]


def test_cannot_attach_other_schools_objects(client, admin, admin_b):
    b_class = client.get("/api/classes", headers=admin_b).json()[0]
    b_section = client.get("/api/sections", headers=admin_b).json()[0]
    b_teacher = client.get("/api/teachers", headers=admin_b).json()["items"][0]
    b_subject = client.get("/api/subjects", headers=admin_b).json()[0]
    a_section = client.get("/api/sections", headers=admin).json()[0]
    a_teacher = client.get("/api/teachers", headers=admin).json()["items"][0]
    a_class = client.get("/api/classes", headers=admin).json()[0]
    body = {"admission_no": "X-1", "full_name": "x", "dob": "2010-01-01", "parent_mobile": "9222222222"}
    assert client.post("/api/students", headers=admin, json={**body, "class_id": b_class["id"], "section_id": b_section["id"]}).status_code == 404
    assert client.post("/api/students", headers=admin, json={**body, "class_id": a_class["id"], "section_id": b_section["id"]}).status_code == 404
    assert client.post("/api/sections", headers=admin, json={"class_id": b_class["id"], "name": "Q"}).status_code == 404
    assert client.patch(f"/api/sections/{a_section['id']}", headers=admin, json={"class_teacher_id": b_teacher["id"]}).status_code == 404
    assert client.post("/api/assignments", headers=admin, json={"teacher_id": b_teacher["id"], "section_id": a_section["id"], "subject_id": b_subject["id"]}).status_code == 404
    assert client.post("/api/assignments", headers=admin, json={"teacher_id": a_teacher["id"], "section_id": b_section["id"], "subject_id": b_subject["id"]}).status_code == 404


def test_same_login_ids_resolve_to_own_school_only(client):
    ha = login(client, "EDN01", "teacher", "T-001", "teacher123")
    hb = login(client, "OTHER", "teacher", "T-001", "teacher123")
    a, b = client.get("/api/auth/me", headers=ha).json(), client.get("/api/auth/me", headers=hb).json()
    assert a["school"]["code"] == "EDN01" and b["school"]["code"] == "OTHER" and a["id"] != b["id"]
    assert a["teacher_id"] != b["teacher_id"]
    # parent OTP is school-scoped too
    pa, ta = parent_login(client, "EDN01", "9000000001")
    pb, tb = parent_login(client, "OTHER", "9000000001")
    assert ta["user"]["school"]["code"] == "EDN01" and tb["user"]["school"]["code"] == "OTHER"
    ka = {k["id"] for k in client.get("/api/me/children", headers=pa).json()}
    kb = {k["id"] for k in client.get("/api/me/children", headers=pb).json()}
    assert ka and kb and ka.isdisjoint(kb)


def test_wrong_school_code_cannot_login(client):
    r = client.post("/api/auth/login", json={"school_code": "OTHER", "role": "admin", "login_id": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_school_b_token_cannot_read_school_a_ids(client, admin_b):
    # school-B token against school-A object ids: ids exist, but only in A
    a_students = client.get("/api/students", headers=login(client, "EDN01", "admin", "admin", "admin123")).json()["items"]
    for s in a_students:
        assert client.get(f"/api/students/{s['id']}", headers=admin_b).status_code == 404


def test_orm_guard_filters_even_without_explicit_school_filter(Session, client):
    """Second line of defence: with session.info['school_id'] set, a query that FORGOT its WHERE school_id
    still only returns that school's rows (SQLAlchemy do_orm_execute + with_loader_criteria)."""
    with Session() as db:
        sid_a = db.scalar(select(Subject.school_id).order_by(Subject.id))
        total = len(db.scalars(select(Student)).all())
        assert total == 18  # 9 per school, no guard yet
        db.info["school_id"] = sid_a
        assert {s.school_id for s in db.scalars(select(Student)).all()} == {sid_a}
        assert len(db.scalars(select(Student)).all()) == 9
        assert {p.school_id for p in db.scalars(select(Parent)).all()} == {sid_a}
        assert {u.school_id for u in db.scalars(select(User)).all()} == {sid_a}  # also hides the superadmin row
        # joins are covered as well
        rows = db.execute(select(Student, User).join(User, User.id == Student.user_id)).all()
        assert len(rows) == 9 and all(s.school_id == sid_a and u.school_id == sid_a for s, u in rows)
        # and bulk UPDATE/DELETE cannot touch the other school
        from sqlalchemy import update

        db.execute(update(Student).values(address="changed"))
        db.commit()
        db.info.pop("school_id")
        changed = db.scalars(select(Student).where(Student.address == "changed")).all()
        assert len(changed) == 9 and {s.school_id for s in changed} == {sid_a}


# =============================================================================================== Phase 2
# Every Phase 2 table gets rows in BOTH schools (identical logins), then school A pokes at B's ids.
import pytest  # noqa: E402

from app import models as m  # noqa: E402
from tests.conftest import png_bytes, section_id, student_ids, student_login, subject_id, teacher_login  # noqa: E402
from datetime import date, timedelta  # noqa: E402

TODAY = date.today().isoformat()
FUT = lambda n: (date.today() + timedelta(days=n)).isoformat()  # noqa: E731


def _populate(client, code):
    """Create one row in every Phase 2 table for school `code`; returns the ids + auth headers used."""
    adm = login(client, code, "admin", "admin", "admin123")
    tch = teacher_login(client, code, "T-001")
    stu = student_login(client, code, "EN-26-001", "15082010")
    par, _ = parent_login(client, code, "9000000001")
    sec, st, maths = section_id(client, adm), student_ids(client, adm), subject_id(client, adm, "Mathematics")
    recs = [{"student_id": st["EN-26-001"], "status": "absent"}, {"student_id": st["EN-26-002"], "status": "present"}]
    assert client.put("/api/attendance/sessions", headers=tch, json={"section_id": sec, "date": TODAY, "records": recs}).status_code == 200
    up = client.post("/api/timetable/uploads", headers=tch, data={"section_id": sec}, files={"file": ("t.png", png_bytes(), "image/png")}).json()
    hw = client.post("/api/homework", headers=tch, data={"section_id": sec, "subject_id": maths, "title": "HW", "due_date": FUT(2)}, files={"file": ("h.png", png_bytes(), "image/png")}).json()
    sub = client.post(f"/api/homework/{hw['id']}/submissions", headers=stu, data={"text": "a"}, files={"file": ("s.png", png_bytes(), "image/png")}).json()
    lv = client.post("/api/leave", headers=stu, data={"leave_type": "sick", "from_date": FUT(1), "to_date": FUT(2)}).json()
    client.post(f"/api/leave/{lv['id']}/decision", headers=par, json={"decision": "approve"})  # -> leave_approvals row
    period = client.get("/api/periods", headers=adm).json()[0]
    entry = client.get(f"/api/timetable/sections/{sec}", headers=adm).json()["entries"][0]
    notif = client.get("/api/notifications", headers=par).json()[0]
    # Phase 3: a quiz + submitted attempt (+answers), an exam with a paper and marks
    from tests.test_assessment import answers_for, exam_body, fill_marks, make_pdf, new_quiz

    qid = new_quiz(client, adm, tch)
    play = client.post(f"/api/quizzes/{qid}/attempts", headers=stu).json()
    client.post(f"/api/attempts/{play['attempt_id']}/submit", headers=stu, json={"answers": answers_for(play)})
    eid = client.post("/api/exams", headers=tch, json=exam_body(client, adm)).json()["id"]
    client.post(f"/api/exams/{eid}/papers", headers=tch, data={"kind": "paper"}, files={"file": ("p.pdf", make_pdf(["x"]), "application/pdf")})
    fill_marks(client, tch, eid, {"EN-26-001": 30})
    return dict(qid=qid, aid=play["attempt_id"], eid=eid, adm=adm, tch=tch, stu=stu, par=par, sec=sec, st=st, up=up, hw=hw, sub=sub, lv=lv, period=period, entry=entry,
                notif=notif, maths=maths)  # fmt: skip


@pytest.fixture()
def two_schools(client):
    return _populate(client, "EDN01"), _populate(client, "OTHER")


def test_phase2_orm_guard_every_tenant_table(Session, two_schools):
    """For EVERY TenantMixin table (not just a hand-picked list): both schools have rows, and with the session guard
    on, a query that forgets its WHERE school_id sees only one school. New tables are picked up automatically."""
    models = [c for c in m.Base.__subclasses__() if issubclass(c, m.TenantMixin) and c is not m.User]
    phase2 = {m.Notification, m.AttendanceSession, m.AttendanceRecord, m.Period, m.TimetableEntry, m.TimetableUpload, m.Homework,
              m.HomeworkSubmission, m.LeaveRequest, m.LeaveApproval}  # fmt: skip
    phase3 = {m.Quiz, m.QuizQuestion, m.QuizAttempt, m.AttemptAnswer, m.Exam, m.ExamPaper, m.Mark}
    assert phase2 | phase3 <= set(models)
    with Session() as db:
        sid_a = db.scalar(select(m.School.id).where(m.School.code == "EDN01"))
        for cls in models:
            schools = {r for r in db.scalars(select(cls.school_id))}
            assert len(schools) == 2, f"{cls.__name__} has no rows in one of the schools (test would be vacuous)"
        db.info["school_id"] = sid_a
        for cls in models:
            assert {r for r in db.scalars(select(cls.school_id))} == {sid_a}, f"{cls.__name__} leaks across schools"


def test_phase2_cannot_touch_other_schools_rows_by_id(client, two_schools):
    a, b = two_schools
    ha, hb = a["adm"], b["adm"]
    # attendance
    assert client.get(f"/api/attendance/sheet?section_id={b['sec']}&date={TODAY}", headers=a["tch"]).status_code == 404
    assert client.get(f"/api/attendance/sheet?section_id={b['sec']}&date={TODAY}", headers=ha).status_code == 404
    assert client.get(f"/api/attendance/students/{b['st']['EN-26-001']}", headers=ha).status_code == 404
    assert client.get(f"/api/attendance/students/{b['st']['EN-26-001']}", headers=a["stu"]).status_code == 404
    recs = [{"student_id": b["st"]["EN-26-001"], "status": "present"}]
    assert client.put("/api/attendance/sessions", headers=a["tch"], json={"section_id": b["sec"], "date": TODAY, "records": recs}).status_code == 404
    assert client.put("/api/attendance/sessions", headers=a["tch"], json={"section_id": a["sec"], "date": TODAY, "records": recs}).status_code == 422
    assert client.put("/api/attendance/sessions", headers=ha, json={"section_id": a["sec"], "date": TODAY, "records": [
        {"student_id": a["st"]["EN-26-001"], "status": "present"}], "subject_id": b["maths"]}).status_code == 404
    sa = client.get(f"/api/attendance/summary?date={TODAY}", headers=ha).json()
    assert {r["section_id"] for r in sa}.isdisjoint({r["section_id"] for r in client.get(f"/api/attendance/summary?date={TODAY}", headers=hb).json()})
    # B's parent got B's alert only; A's parent only A's
    assert {n["id"] for n in client.get("/api/notifications", headers=a["par"]).json()}.isdisjoint(
        {n["id"] for n in client.get("/api/notifications", headers=b["par"]).json()})
    assert client.post(f"/api/notifications/{b['notif']['id']}/read", headers=a["par"]).status_code == 404
    # periods / timetable
    assert {p["id"] for p in client.get("/api/periods", headers=ha).json()}.isdisjoint({p["id"] for p in client.get("/api/periods", headers=hb).json()})
    assert client.patch(f"/api/periods/{b['period']['id']}", headers=ha, json={"label": "pwned"}).status_code == 404
    assert client.delete(f"/api/periods/{b['period']['id']}", headers=ha).status_code == 404
    assert client.get(f"/api/timetable/sections/{b['sec']}", headers=ha).status_code == 404
    assert client.delete(f"/api/timetable/entries/{b['entry']['id']}", headers=ha).status_code == 404
    body = {"section_id": a["sec"], "day": 0, "period_id": b["period"]["id"], "subject_id": a["maths"]}
    assert client.put("/api/timetable/entries", headers=ha, json=body).status_code == 404  # B's period
    assert client.put("/api/timetable/entries", headers=ha, json={**body, "period_id": a["period"]["id"], "section_id": b["sec"]}).status_code == 404
    assert client.put("/api/timetable/entries", headers=ha, json={**body, "period_id": a["period"]["id"], "subject_id": b["maths"]}).status_code == 404
    assert client.post("/api/timetable/uploads", headers=a["tch"], data={"section_id": b["sec"], "text": "x"}).status_code == 404
    assert client.get(f"/api/timetable/uploads/{b['up']['id']}/file", headers=ha).status_code == 404
    assert client.get(f"/api/timetable/uploads/{b['up']['id']}/file", headers=a["stu"]).status_code == 404
    assert client.delete(f"/api/timetable/uploads/{b['up']['id']}", headers=ha).status_code == 404
    # homework
    assert client.get(f"/api/homework/{b['hw']['id']}", headers=ha).status_code == 404
    assert client.get(f"/api/homework/{b['hw']['id']}/attachment", headers=a["stu"]).status_code == 404
    assert client.get(f"/api/homework/{b['hw']['id']}/submissions", headers=ha).status_code == 404
    assert client.get(f"/api/homework/{b['hw']['id']}/submissions", headers=a["tch"]).status_code == 404
    assert client.delete(f"/api/homework/{b['hw']['id']}", headers=ha).status_code == 404
    assert client.post(f"/api/homework/{b['hw']['id']}/submissions", headers=a["stu"], data={"text": "x"}).status_code == 404
    assert client.get(f"/api/homework/submissions/{b['sub']['id']}/file", headers=ha).status_code == 404
    assert client.patch(f"/api/homework/submissions/{b['sub']['id']}/review", headers=a["tch"], json={"feedback": "pwned"}).status_code == 404
    mk = {"section_id": b["sec"], "subject_id": b["maths"], "title": "x", "due_date": FUT(1)}
    assert client.post("/api/homework", headers=a["tch"], data=mk).status_code == 404
    assert {h["id"] for h in client.get("/api/homework", headers=ha).json()}.isdisjoint({b["hw"]["id"]})
    kid_b = b["st"]["EN-26-001"]
    assert client.get(f"/api/homework?child_id={kid_b}", headers=a["par"]).status_code == 422
    # leave
    assert client.get(f"/api/leave/{b['lv']['id']}", headers=ha).status_code == 404
    assert client.get(f"/api/leave/{b['lv']['id']}/attachment", headers=ha).status_code == 404
    assert client.post(f"/api/leave/{b['lv']['id']}/decision", headers=a["tch"], json={"decision": "approve"}).status_code == 404
    assert client.post(f"/api/leave/{b['lv']['id']}/decision", headers=a["par"], json={"decision": "reject"}).status_code == 404
    assert client.post(f"/api/leave/{b['lv']['id']}/cancel", headers=a["stu"]).status_code == 404
    assert {x["id"] for x in client.get("/api/leave", headers=ha).json()}.isdisjoint({b["lv"]["id"]})
    assert {x["id"] for x in client.get("/api/leave", headers=a["tch"]).json()}.isdisjoint({b["lv"]["id"]})
    # ID card
    assert client.get(f"/api/students/{kid_b}/id-card", headers=ha).status_code == 404
    assert client.get(f"/api/students/{kid_b}/id-card/qr.png", headers=a["stu"]).status_code == 404
    pb = client.get(f"/api/students/{kid_b}/id-card", headers=hb).json()["qr_payload"]
    assert client.post("/api/id/verify", headers=a["tch"], json={"payload": pb}).json()["reason"] == "wrong_school"
    # B's untouched
    assert client.get(f"/api/homework/{b['hw']['id']}", headers=hb).json()["title"] == "HW"
    assert client.get(f"/api/leave/{b['lv']['id']}", headers=b["stu"]).json()["status"] == "pending_teacher"


def test_phase2_uploaded_files_are_school_scoped_on_disk(two_schools):
    import os
    from app.config import get_settings
    a, b = two_schools
    root = get_settings().upload_dir
    assert os.path.isdir(os.path.join(root, "1")) and os.path.isdir(os.path.join(root, "2"))


def test_phase3_assessment_is_school_scoped(client, admin, admin_b, teacher, teacher_b, student1_b):
    """Quizzes, attempts, exams, marks, papers and report cards of school B are invisible and untouchable from school A."""
    from tests.test_assessment import QUESTIONS, exam_body, fill_marks, make_pdf, new_quiz, quiz_body, answers_for

    qid_b = new_quiz(client, admin_b, teacher_b)
    play_b = client.post(f"/api/quizzes/{qid_b}/attempts", headers=student1_b).json()
    client.post(f"/api/attempts/{play_b['attempt_id']}/submit", headers=student1_b, json={"answers": answers_for(play_b)})
    eid_b = client.post("/api/exams", headers=teacher_b, json=exam_body(client, admin_b)).json()["id"]
    fill_marks(client, teacher_b, eid_b, {"EN-26-001": 30})
    client.post(f"/api/exams/{eid_b}/papers", headers=teacher_b, data={"kind": "paper"}, files={"file": ("p.pdf", make_pdf(["x"]), "application/pdf")})
    b_student = client.get("/api/students", headers=admin_b).json()["items"][0]
    answer_b = client.get(f"/api/attempts/{play_b['attempt_id']}", headers=admin_b).json()["answers"][-1]["answer_id"]

    # school A (admin AND teacher with the same login ids) gets 404 on every B id, never 200/403-with-data
    for h in (admin, teacher):
        assert client.get(f"/api/quizzes/{qid_b}", headers=h).status_code == 404
        assert client.get(f"/api/quizzes/{qid_b}/attempts", headers=h).status_code == 404
        assert client.get(f"/api/attempts/{play_b['attempt_id']}", headers=h).status_code == 404
        assert client.get(f"/api/exams/{eid_b}", headers=h).status_code == 404
        assert client.get(f"/api/exams/{eid_b}/marks", headers=h).status_code == 404
        assert client.get(f"/api/exams/{eid_b}/papers/paper", headers=h).status_code == 404
        assert client.get(f"/api/report-card?student_id={b_student['id']}", headers=h).status_code == 404
    assert client.post(f"/api/quizzes/{qid_b}/publish", headers=teacher).status_code == 404
    assert client.delete(f"/api/quizzes/{qid_b}", headers=admin).status_code == 404
    assert client.put(f"/api/quizzes/{qid_b}", headers=teacher, json=quiz_body(client, admin)).status_code == 404
    assert client.patch(f"/api/attempts/answers/{answer_b}/grade", headers=teacher, json={"marks": 1}).status_code == 404
    assert client.put(f"/api/exams/{eid_b}/marks", headers=teacher, json={"rows": []}).status_code == 404
    assert client.post(f"/api/exams/{eid_b}/publish", headers=admin).status_code == 404
    assert client.post(f"/api/exams/{eid_b}/unpublish", headers=admin).status_code == 404
    assert client.delete(f"/api/exams/{eid_b}", headers=admin).status_code == 404
    # lists contain only own-school rows
    a_q = {x["id"] for x in client.get("/api/quizzes", headers=teacher).json()}
    a_e = {x["id"] for x in client.get("/api/exams", headers=admin).json()}
    assert qid_b not in a_q and eid_b not in a_e
    # cannot create against school B's section/subject
    b_sec = client.get("/api/sections", headers=admin_b).json()[0]["id"]
    b_sub = client.get("/api/subjects", headers=admin_b).json()[0]["id"]
    assert client.post("/api/quizzes", headers=teacher, json={**quiz_body(client, admin, QUESTIONS), "section_id": b_sec}).status_code == 404
    assert client.post("/api/exams", headers=teacher, json={**exam_body(client, admin), "subject_id": b_sub}).status_code == 404
    # B's data is intact
    assert client.get(f"/api/exams/{eid_b}/marks", headers=admin_b).json()["stats"]["entered"] == 1
    assert client.get(f"/api/attempts/{play_b['attempt_id']}", headers=admin_b).json()["score"] > 0
