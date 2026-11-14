from datetime import date, timedelta

from tests.conftest import png_bytes, section_id, student_ids, subject_id

DUE = (date.today() + timedelta(days=3)).isoformat()


def post_hw(client, h, sec, sub, title="Fractions worksheet", due=DUE, **extra):
    return client.post("/api/homework", headers=h, data={"section_id": sec, "subject_id": sub, "title": title, "description": "Do Q1-10", "due_date": due}, **extra)


def test_full_homework_flow(client, admin, teacher, student1, parent1):
    sec, maths = section_id(client, admin), subject_id(client, admin, "Mathematics")
    r = post_hw(client, teacher, sec, maths, files={"file": ("sheet.png", png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    hw = r.json()
    assert hw["total_students"] == 8 and hw["submitted_count"] == 0 and hw["attachment_name"] == "sheet.png"
    hid = hw["id"]
    # student sees it, with no submission yet; can download the attachment
    mine = client.get("/api/homework", headers=student1).json()
    assert [h["id"] for h in mine] == [hid] and mine[0]["my_submission"] is None and mine[0]["total_students"] is None
    assert client.get(f"/api/homework/{hid}/attachment", headers=student1).content == png_bytes()
    # parent must name a child; sees pending status for that child
    assert client.get("/api/homework", headers=parent1).status_code == 422
    st = student_ids(client, admin)
    kid = client.get(f"/api/homework?child_id={st['EN-26-001']}", headers=parent1).json()
    assert kid[0]["my_submission"] is None
    assert client.get(f"/api/homework?child_id={st['EN-26-009']}", headers=parent1).json() == []  # other child, other section
    assert client.get(f"/api/homework?child_id={st['EN-26-002']}", headers=parent1).status_code == 422  # not her child
    # submit: empty rejected; text ok; photo upload replaces; PDF/voice accepted; html rejected
    assert client.post(f"/api/homework/{hid}/submissions", headers=student1, data={"text": ""}).status_code == 422
    assert client.post(f"/api/homework/{hid}/submissions", headers=student1, data={"text": "x"}, files={"file": ("a.html", b"<script>1</script>", "text/html")}).status_code == 415
    r = client.post(f"/api/homework/{hid}/submissions", headers=student1, data={"text": "my answers"})
    assert r.status_code == 201 and r.json()["status"] == "submitted" and not r.json()["is_late"]
    r = client.post(f"/api/homework/{hid}/submissions", headers=student1, data={"text": "v2"}, files={"file": ("ans.png", png_bytes((1, 2, 3)), "image/png")})
    assert r.status_code == 201 and r.json()["text"] == "v2" and r.json()["original_name"] == "ans.png"
    sub_id = r.json()["id"]
    assert client.post(f"/api/homework/{hid}/submissions", headers=student1, files={"file": ("v.ogg", b"OggS\x00\x02rest", "audio/ogg")}).status_code == 201
    assert client.post(f"/api/homework/{hid}/submissions", headers=student1, files={"file": ("d.pdf", b"%PDF-1.4 hi", "application/pdf")}).status_code == 201
    # teacher sees roll with 1 submitted, 7 pending
    rows = client.get(f"/api/homework/{hid}/submissions", headers=teacher).json()
    assert len(rows) == 8 and sum(1 for x in rows if x["submission"]) == 1
    assert client.get(f"/api/homework/{hid}", headers=teacher).json()["submitted_count"] == 1
    assert client.get(f"/api/homework/submissions/{sub_id}/file", headers=teacher).status_code == 200
    assert client.get(f"/api/homework/submissions/{sub_id}/file", headers=parent1).status_code == 200
    # review -> student and parent notified; reviewed is final
    r = client.patch(f"/api/homework/submissions/{sub_id}/review", headers=teacher, json={"status": "returned", "feedback": "Show working", "grade": "B"})
    assert r.status_code == 200 and r.json()["status"] == "returned"
    assert [n["key"] for n in client.get("/api/notifications", headers=student1).json()] == ["notif.homework_returned"]
    assert [n["key"] for n in client.get("/api/notifications", headers=parent1).json()] == ["notif.homework_returned"]
    assert client.post(f"/api/homework/{hid}/submissions", headers=student1, data={"text": "fixed"}).status_code == 201  # resubmit after return
    client.patch(f"/api/homework/submissions/{sub_id}/review", headers=teacher, json={"status": "reviewed", "grade": "A"})
    assert client.post(f"/api/homework/{hid}/submissions", headers=student1, data={"text": "again"}).status_code == 409
    done = client.get(f"/api/homework?child_id={st['EN-26-001']}", headers=parent1).json()[0]["my_submission"]
    assert done["status"] == "reviewed" and done["grade"] == "A"
    # admin sees completion counts, read-only
    adm = client.get("/api/homework", headers=admin).json()[0]
    assert adm["submitted_count"] == 1 and adm["reviewed_count"] == 1
    assert client.get(f"/api/homework/{hid}/submissions", headers=admin).status_code == 200
    assert client.patch(f"/api/homework/submissions/{sub_id}/review", headers=admin, json={}).status_code == 403
    assert post_hw(client, admin, sec, maths).status_code == 403
    # delete cleans up
    assert client.delete(f"/api/homework/{hid}", headers=teacher).status_code == 204
    assert client.get("/api/homework", headers=student1).json() == []


def test_late_flag_and_validation(client, admin, teacher, student1):
    sec, maths = section_id(client, admin), subject_id(client, admin, "Mathematics")
    assert post_hw(client, teacher, sec, maths, due=(date.today() - timedelta(days=1)).isoformat()).status_code == 422  # past due
    assert post_hw(client, teacher, sec, subject_id(client, admin, "Science")).status_code == 403  # T-001 doesn't teach Science
    assert post_hw(client, teacher, section_id(client, admin, "10-B"), maths).status_code == 201  # but teaches Maths in 10-B
    assert post_hw(client, teacher, sec, 999999).status_code == 404
    assert client.post("/api/homework", headers=teacher, data={"section_id": sec, "subject_id": maths, "title": "x", "due_date": "garbage"}).status_code == 422
    hid = post_hw(client, teacher, sec, maths).json()["id"]
    from app.models import Homework
    # make it overdue directly in the DB, then submit
    import app.main  # noqa: F401
    from app.db import get_db
    db = next(app.main.app.dependency_overrides[get_db]())
    h = db.get(Homework, hid)
    h.due_date = date.today() - timedelta(days=1)
    db.commit()
    assert client.post(f"/api/homework/{hid}/submissions", headers=student1, data={"text": "late one"}).json()["is_late"] is True


def test_homework_rbac(client, admin, teacher, teacher2, student1, parent1):
    sec, maths = section_id(client, admin), subject_id(client, admin, "Mathematics")
    hid = post_hw(client, teacher, sec, maths).json()["id"]
    # another teacher can't read, review, delete, or list it
    assert client.get(f"/api/homework/{hid}", headers=teacher2).status_code == 403
    assert client.get(f"/api/homework/{hid}/submissions", headers=teacher2).status_code == 403
    assert client.delete(f"/api/homework/{hid}", headers=teacher2).status_code == 403
    assert client.get("/api/homework", headers=teacher2).json() == []
    # student of another section can't submit / read it (Ishaan 9-A)
    from tests.conftest import student_login
    s9 = student_login(client, "EDN01", "EN-26-009", "20052011")
    assert client.get(f"/api/homework/{hid}", headers=s9).status_code == 403
    assert client.post(f"/api/homework/{hid}/submissions", headers=s9, data={"text": "x"}).status_code == 403
    assert client.get("/api/homework", headers=s9).json() == []
    # parent/teacher can't submit
    assert client.post(f"/api/homework/{hid}/submissions", headers=parent1, data={"text": "x"}).status_code == 403
    assert client.post(f"/api/homework/{hid}/submissions", headers=teacher, data={"text": "x"}).status_code == 403
    # student can't see classmate's submission file
    sid_ = client.post(f"/api/homework/{hid}/submissions", headers=student1, data={"text": "mine"}, files={"file": ("a.png", png_bytes(), "image/png")}).json()["id"]
    s2 = student_login(client, "EDN01", "EN-26-002", "22032010")
    assert client.get(f"/api/homework/submissions/{sid_}/file", headers=s2).status_code == 403
    assert client.patch(f"/api/homework/submissions/{sid_}/review", headers=student1, json={}).status_code == 403
