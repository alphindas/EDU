from datetime import date, timedelta

from tests.conftest import login, parent_login, student_ids, student_login, teacher_login


def d(n):
    return (date.today() + timedelta(days=n)).isoformat()


def apply(client, h, a=1, b=2, **kw):
    return client.post("/api/leave", headers=h, data={"leave_type": "sick", "from_date": d(a), "to_date": d(b), "reason": "fever", **kw})


def decide(client, h, rid, decision="approve", comment=""):
    return client.post(f"/api/leave/{rid}/decision", headers=h, json={"decision": decision, "comment": comment})


# ------------------------------------------------------------------------------------ student chain
def test_student_leave_chain_parent_then_class_teacher_then_admin_view(client, admin, teacher, teacher2, student1, parent1):
    r = apply(client, student1)
    assert r.status_code == 201, r.text
    lv = r.json()
    rid = lv["id"]
    assert lv["status"] == "pending_parent" and lv["days"] == 2 and lv["can_cancel"] and not lv["can_act"]
    # parent notified; class teacher and admin cannot see it yet, and cannot decide it
    assert [n["key"] for n in client.get("/api/notifications", headers=parent1).json()] == ["notif.leave_needs_parent"]
    assert client.get("/api/leave", headers=teacher).json() == []
    assert client.get("/api/leave", headers=admin).json() == []
    assert client.get(f"/api/leave/{rid}", headers=teacher).status_code == 404
    assert decide(client, teacher, rid).status_code == 404
    assert decide(client, student1, rid).status_code == 403  # applicant can't approve own
    # wrong parent: parent of another child
    p2, _ = parent_login(client, "EDN01", "9000000002")
    assert decide(client, p2, rid).status_code == 404
    assert client.get("/api/leave", headers=p2).json() == []
    # parent approves -> pending_teacher
    mine = client.get("/api/leave", headers=parent1).json()[0]
    assert mine["can_act"]
    r = decide(client, parent1, rid, comment="ok")
    assert r.status_code == 200 and r.json()["status"] == "pending_teacher" and r.json()["approvals"][0]["step"] == "parent"
    assert decide(client, parent1, rid).status_code == 403  # parent's turn is over
    # class teacher of 10-A is T-001; T-002 (other class teacher) can't see or act; admin can't act
    assert client.get(f"/api/leave/{rid}", headers=teacher2).status_code == 404
    assert decide(client, teacher2, rid).status_code == 404
    assert client.get("/api/leave", headers=admin).json() == []  # still hidden from admin until fully approved
    assert [n["key"] for n in client.get("/api/notifications", headers=teacher).json()] == ["notif.leave_needs_teacher"]
    assert client.get("/api/leave", headers=teacher).json()[0]["can_act"]
    r = decide(client, teacher, rid, comment="approved")
    assert r.status_code == 200 and r.json()["status"] == "approved" and [a["step"] for a in r.json()["approvals"]] == ["parent", "teacher"]
    # admin now sees it, VIEW ONLY
    v = client.get("/api/leave", headers=admin).json()
    assert [x["id"] for x in v] == [rid] and v[0]["can_act"] is False
    assert decide(client, admin, rid, "reject").status_code == 403
    assert decide(client, teacher, rid).status_code == 409  # not pending anymore
    keys = [n["key"] for n in client.get("/api/notifications", headers=student1).json()]
    assert "notif.leave_approved" in keys and "notif.leave_parent_approved" in keys


def test_student_leave_rejections_and_cancel(client, admin, teacher, student1, parent1):
    rid = apply(client, student1).json()["id"]
    r = decide(client, parent1, rid, "reject", "not now")
    assert r.json()["status"] == "rejected" and r.json()["approvals"][0]["comment"] == "not now"
    assert client.get("/api/leave", headers=teacher).json() == []  # parent-rejected never reaches the teacher
    # new request: teacher rejects -> teacher sees it as rejected, admin does not
    rid2 = apply(client, student1, 5, 6).json()["id"]
    decide(client, parent1, rid2)
    assert decide(client, teacher, rid2, "reject").json()["status"] == "rejected"
    assert [x["status"] for x in client.get("/api/leave", headers=teacher).json()] == ["rejected"]
    assert client.get("/api/leave", headers=admin).json() == []
    # cancel
    rid3 = apply(client, student1, 10, 11).json()["id"]
    assert client.post(f"/api/leave/{rid3}/cancel", headers=parent1).status_code == 403
    assert client.post(f"/api/leave/{rid3}/cancel", headers=student1).json()["status"] == "cancelled"
    assert client.post(f"/api/leave/{rid3}/cancel", headers=student1).status_code == 409
    assert decide(client, parent1, rid3).status_code == 409


def test_leave_validation(client, student1, teacher):
    assert client.post("/api/leave", headers=student1, data={"leave_type": "vacation", "from_date": d(1), "to_date": d(2)}).status_code == 422
    assert apply(client, student1, 3, 2).status_code == 422
    assert apply(client, student1, 1, 200).status_code == 422
    assert apply(client, student1, 1, 3).status_code == 201
    assert apply(client, student1, 3, 5).status_code == 409  # overlaps (3)
    assert apply(client, student1, 4, 5).status_code == 201
    r = apply(client, student1, 20, 21, **{})
    assert r.status_code == 201
    from tests.conftest import png_bytes
    r = client.post("/api/leave", headers=student1, data={"leave_type": "sick", "from_date": d(30), "to_date": d(30)}, files={"file": ("note.png", png_bytes(), "image/png")})
    assert r.status_code == 201 and r.json()["attachment_name"] == "note.png"
    assert client.get(f"/api/leave/{r.json()['id']}/attachment", headers=student1).content == png_bytes()
    bad = client.post("/api/leave", headers=student1, data={"leave_type": "sick", "from_date": d(40), "to_date": d(40)}, files={"file": ("x.exe", b"MZ..", "application/octet-stream")})
    assert bad.status_code == 415


def test_parent_and_admin_cannot_apply(client, admin, parent1):
    assert apply(client, admin).status_code == 403
    assert apply(client, parent1).status_code == 403


# ------------------------------------------------------------------------------------ teacher chain
def test_teacher_leave_admin_decides(client, admin, teacher, teacher2, student1):
    rid = apply(client, teacher).json()["id"]
    assert client.get(f"/api/leave/{rid}", headers=teacher).json()["status"] == "pending_admin"
    assert [n["key"] for n in client.get("/api/notifications", headers=admin).json()] == ["notif.leave_needs_admin"]
    # other teachers/students can't see or decide; applicant can't self-approve
    assert client.get(f"/api/leave/{rid}", headers=teacher2).status_code == 404
    assert decide(client, teacher, rid).status_code == 403
    assert decide(client, teacher2, rid).status_code == 404
    assert client.get("/api/leave", headers=student1).json() == []
    lst = client.get("/api/leave", headers=admin).json()
    assert lst[0]["can_act"] and lst[0]["applicant_role"] == "teacher"
    r = decide(client, admin, rid, "approve", "enjoy")
    assert r.json()["status"] == "approved" and r.json()["approvals"][0]["step"] == "admin"
    assert "notif.leave_approved" in [n["key"] for n in client.get("/api/notifications", headers=teacher).json()]
    # rejection path
    rid2 = apply(client, teacher, 10, 11).json()["id"]
    assert decide(client, admin, rid2, "reject", "exams").json()["status"] == "rejected"


def test_class_teacher_cannot_approve_own_leave_via_student_path(client, teacher):
    rid = apply(client, teacher).json()["id"]
    assert decide(client, teacher, rid).status_code == 403


# ------------------------------------------------------------------------------------ ID card
def test_id_card_qr_and_verify(client, admin, teacher, student1, parent1):
    st = student_ids(client, admin)
    card = client.get(f"/api/students/{st['EN-26-001']}/id-card", headers=student1).json()
    assert card["full_name"] == "Aarav Reddy" and card["class_name"] == "10" and card["section_name"] == "A"
    assert card["school_code"] == "EDN01" and card["qr_payload"].startswith("EDN1.EDN01.EN-26-001.")
    png = client.get(f"/api/students/{st['EN-26-001']}/id-card/qr.png", headers=student1)
    assert png.status_code == 200 and png.headers["content-type"] == "image/png" and png.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.get(f"/api/students/{st['EN-26-001']}/id-card", headers=parent1).status_code == 200
    assert client.get(f"/api/students/{st['EN-26-009']}/id-card", headers=parent1).status_code == 200  # sibling
    assert client.get(f"/api/students/{st['EN-26-002']}/id-card", headers=student1).status_code == 403
    assert client.get(f"/api/students/{st['EN-26-002']}/id-card", headers=parent1).status_code == 403
    assert client.get(f"/api/students/{st['EN-26-002']}/id-card/qr.png", headers=parent1).status_code == 403
    assert client.get(f"/api/students/{st['EN-26-001']}/id-card").status_code == 401
    # verify (staff only)
    ok = client.post("/api/id/verify", headers=teacher, json={"payload": card["qr_payload"]}).json()
    assert ok["valid"] and ok["student"]["admission_no"] == "EN-26-001"
    assert client.post("/api/id/verify", headers=student1, json={"payload": card["qr_payload"]}).status_code == 403
    forged = card["qr_payload"].rsplit(".", 1)[0] + ".AAAAAAAAAAAAAAAA"
    assert client.post("/api/id/verify", headers=teacher, json={"payload": forged}).json() == {"valid": False, "reason": "bad_signature", "student": None}
    # someone who only knows the admission number can't mint a card for another student
    guess = f"EDN1.EDN01.EN-26-002.{card['qr_payload'].rsplit('.', 1)[1]}"
    assert client.post("/api/id/verify", headers=teacher, json={"payload": guess}).json()["reason"] == "bad_signature"
    assert client.post("/api/id/verify", headers=teacher, json={"payload": "garbage"}).json()["reason"] == "malformed"
