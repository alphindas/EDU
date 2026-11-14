from datetime import date, timedelta

import httpx

from app import vision
from tests.conftest import parent_login, section_id, student_ids

TODAY = date.today().isoformat()


def mark(client, h, sec, students, statuses, d=TODAY, period=0, **kw):
    recs = [{"student_id": students[a], "status": s} for a, s in statuses.items()]
    return client.put("/api/attendance/sessions", headers=h, json={"section_id": sec, "date": d, "period": period, "records": recs, **kw})


def test_teacher_marks_sheet_and_parent_alerted(client, admin, teacher, parent1):
    sec, st = section_id(client, admin), student_ids(client, admin)
    sheet = client.get(f"/api/attendance/sheet?section_id={sec}&date={TODAY}", headers=teacher).json()
    assert not sheet["exists"] and len(sheet["rows"]) == 8 and all(r["status"] is None for r in sheet["rows"])
    r = mark(client, teacher, sec, st, {"EN-26-001": "absent", "EN-26-002": "late", "EN-26-003": "present"})
    assert r.status_code == 200, r.text
    sheet = client.get(f"/api/attendance/sheet?section_id={sec}&date={TODAY}", headers=teacher).json()
    got = {x["admission_no"]: x["status"] for x in sheet["rows"]}
    assert sheet["exists"] and got["EN-26-001"] == "absent" and got["EN-26-004"] is None
    # parent of Aarav got exactly one in-app alert (i18n key + params)
    notes = client.get("/api/notifications", headers=parent1).json()
    assert [n["key"] for n in notes] == ["notif.attendance_absent"] and notes[0]["params"]["name"] == "Aarav Reddy"
    assert client.get("/api/notifications/unread-count", headers=parent1).json()["count"] == 1
    # re-saving the same status does NOT alert again; changing present->absent does
    mark(client, teacher, sec, st, {"EN-26-001": "absent", "EN-26-003": "absent"})
    assert len(client.get("/api/notifications", headers=parent1).json()) == 1
    # marking is an upsert: one session only
    assert client.get(f"/api/attendance/summary?date={TODAY}", headers=admin).json()
    nid = notes[0]["id"]
    assert client.post(f"/api/notifications/{nid}/read", headers=parent1).status_code == 204
    assert client.get("/api/notifications/unread-count", headers=parent1).json()["count"] == 0


def test_summary_counts_for_admin(client, admin, teacher):
    sec, st = section_id(client, admin), student_ids(client, admin)
    mark(client, teacher, sec, st, {"EN-26-001": "absent", "EN-26-002": "late", "EN-26-003": "present", "EN-26-004": "present"})
    row = next(r for r in client.get(f"/api/attendance/summary?date={TODAY}", headers=admin).json() if r["section_id"] == sec)
    assert (row["total"], row["marked"], row["present"], row["absent"], row["late"]) == (8, True, 2, 1, 1)
    other = next(r for r in client.get(f"/api/attendance/summary?date={TODAY}", headers=admin).json() if r["section_id"] != sec)
    assert other["marked"] is False


def test_rbac_and_validation(client, admin, teacher, teacher2, student1, parent1):
    sec, st = section_id(client, admin), student_ids(client, admin)
    sec_b = section_id(client, admin, "10-B")
    assert mark(client, teacher2, sec, st, {"EN-26-001": "present"}).status_code == 200  # T-002 teaches Science in 10-A
    # but T-002 does not teach 9-A
    sec9 = section_id(client, admin, "9-A")
    assert mark(client, teacher2, sec9, st, {"EN-26-009": "present"}).status_code == 403
    assert client.get(f"/api/attendance/sheet?section_id={sec9}&date={TODAY}", headers=teacher2).status_code == 403
    assert mark(client, student1, sec, st, {"EN-26-001": "present"}).status_code == 403
    assert mark(client, parent1, sec, st, {"EN-26-001": "present"}).status_code == 403
    # student from another section is rejected
    assert mark(client, teacher, sec, st, {"EN-26-009": "present"}).status_code == 422
    # future date, duplicate student, unknown subject
    assert mark(client, teacher, sec, st, {"EN-26-001": "present"}, d=(date.today() + timedelta(days=1)).isoformat()).status_code == 422
    dup = client.put("/api/attendance/sessions", headers=teacher, json={"section_id": sec, "date": TODAY, "records": [
        {"student_id": st["EN-26-001"], "status": "present"}, {"student_id": st["EN-26-001"], "status": "absent"}]})
    assert dup.status_code == 422
    assert mark(client, teacher, sec, st, {"EN-26-001": "present"}, subject_id=999999).status_code == 404
    assert client.put("/api/attendance/sessions", headers=teacher, json={"section_id": sec, "date": TODAY, "records": [
        {"student_id": st["EN-26-001"], "status": "sick"}]}).status_code == 422
    assert sec_b  # exists


def test_teacher_backdate_limit_admin_can_correct(client, admin, teacher):
    sec, st = section_id(client, admin), student_ids(client, admin)
    old = (date.today() - timedelta(days=30)).isoformat()
    assert mark(client, teacher, sec, st, {"EN-26-001": "absent"}, d=old).status_code == 403
    assert mark(client, admin, sec, st, {"EN-26-001": "absent"}, d=old).status_code == 200
    assert mark(client, teacher, sec, st, {"EN-26-001": "absent"}, d=(date.today() - timedelta(days=3)).isoformat()).status_code == 200


def test_history_access(client, admin, teacher, student1, parent1):
    sec, st = section_id(client, admin), student_ids(client, admin)
    for i, s in enumerate(["present", "absent", "late", "present"]):
        mark(client, teacher, sec, st, {"EN-26-001": s, "EN-26-002": "present"}, d=(date.today() - timedelta(days=i)).isoformat())
    h = client.get(f"/api/attendance/students/{st['EN-26-001']}", headers=student1).json()
    assert (h["present"], h["absent"], h["late"], h["percentage"]) == (2, 1, 1, 75.0) and len(h["items"]) == 4
    assert client.get(f"/api/attendance/students/{st['EN-26-001']}", headers=parent1).status_code == 200
    assert client.get(f"/api/attendance/students/{st['EN-26-009']}", headers=parent1).status_code == 200  # her other child
    assert client.get(f"/api/attendance/students/{st['EN-26-002']}", headers=student1).status_code == 403  # classmate
    assert client.get(f"/api/attendance/students/{st['EN-26-002']}", headers=parent1).status_code == 403  # not her child
    assert client.get(f"/api/attendance/students/{st['EN-26-002']}", headers=admin).status_code == 200


# ----------------------------------------------------------------------------- face mode bridge
class FakeVision:
    """Stands in for services/vision: records calls, serves canned detections. Includes a student from ANOTHER
    school/section (same register-number scheme) to prove it is dropped."""

    def __init__(self, present, down=False):
        self.running, self.calls, self.present, self.down = False, [], present, down

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("refused")
        self.calls.append((req.method, req.url.path))
        if req.url.path == "/api/status":
            return httpx.Response(200, json={"running": self.running, "demo": True, "present": self.present if self.running else []})
        if req.url.path == "/api/start":
            self.running = True
            return httpx.Response(200, json={"ok": True})
        if req.url.path == "/api/stop":
            self.running = False
            return httpx.Response(200, json={"ok": True})
        if req.url.path == "/api/records":
            return httpx.Response(200, json={"present": self.present, "absent": []})
        return httpx.Response(404)


ROWS = [
    {"Register Number": "EN-26-001", "Name": "Aarav Reddy", "Status": "Present", "Time": "09:01:00", "Confidence": 0.93},
    {"Register Number": "EN-26-002", "Name": "Diya Sharma", "Status": "Late", "Time": "09:20:00", "Confidence": 0.88},
    {"Register Number": "EN-26-009", "Name": "Ishaan Reddy", "Status": "Present", "Confidence": 0.9},  # 9-A, not 10-A
    {"Register Number": "ZZ-99-999", "Name": "Stranger", "Status": "Present"},
]


def test_face_mode_bridge_proposal_then_confirm(client, admin, teacher, parent1):
    fake = FakeVision(ROWS)
    vision._transport = httpx.MockTransport(fake)
    sec, st = section_id(client, admin), student_ids(client, admin)
    r = client.post("/api/attendance/face/start", headers=teacher, json={"section_id": sec, "period": 2})
    assert r.status_code == 200 and r.json()["running"] and r.json()["total"] == 8
    assert ("POST", "/api/start") in fake.calls
    s = client.get(f"/api/attendance/face/status?section_id={sec}", headers=teacher).json()
    assert {d["admission_no"] for d in s["detected"]} == {"EN-26-001", "EN-26-002"} and s["unmatched"] == 2
    stop = client.post(f"/api/attendance/face/stop?section_id={sec}", headers=teacher).json()
    prop = {p["student_id"]: p for p in stop["proposal"]}
    assert len(prop) == 8 and prop[st["EN-26-001"]]["status"] == "present" and prop[st["EN-26-002"]]["status"] == "late"
    assert prop[st["EN-26-003"]]["status"] == "absent" and stop["unmatched"] == 2
    # nothing saved yet
    assert not client.get(f"/api/attendance/sheet?section_id={sec}&date={TODAY}&period=2", headers=teacher).json()["exists"]
    # teacher corrects one (Kabir was actually present) and confirms
    prop[st["EN-26-003"]]["status"] = "present"
    r = client.put("/api/attendance/sessions", headers=teacher, json={"section_id": sec, "date": TODAY, "period": 2, "source": "face",
                                                                        "records": list(prop.values())})
    assert r.status_code == 200 and r.json()["source"] == "face"
    assert client.get("/api/notifications", headers=parent1).json() == []  # Aarav was present -> no alert
    p2, _ = parent_login(client, "EDN01", "9000000002")  # Diya was late -> her parent is alerted
    assert [n["key"] for n in client.get("/api/notifications", headers=p2).json()] == ["notif.attendance_late"]
    assert vision.owner() is None


def test_face_mode_guards(client, admin, teacher, teacher2, student1, admin_b, teacher_b):
    fake = FakeVision(ROWS)
    vision._transport = httpx.MockTransport(fake)
    sec = section_id(client, admin)
    assert client.post("/api/attendance/face/start", headers=student1, json={"section_id": sec}).status_code == 403
    assert client.post("/api/attendance/face/start", headers=admin, json={"section_id": sec}).status_code == 403  # teachers only
    assert client.post("/api/attendance/face/start", headers=teacher2, json={"section_id": section_id(client, admin, "9-A")}).status_code == 403
    assert client.post("/api/attendance/face/start", headers=teacher, json={"section_id": sec}).status_code == 200
    # same class again = idempotent; another school's teacher cannot start, read, or stop it
    assert client.post("/api/attendance/face/start", headers=teacher, json={"section_id": sec}).status_code == 200
    sec_b = section_id(client, admin_b)
    assert client.post("/api/attendance/face/start", headers=teacher_b, json={"section_id": sec_b}).status_code == 409
    assert client.get(f"/api/attendance/face/status?section_id={sec_b}", headers=teacher_b).status_code == 404
    assert client.post(f"/api/attendance/face/stop?section_id={sec_b}", headers=teacher_b).status_code == 404
    assert client.get(f"/api/attendance/face/status?section_id={sec}", headers=teacher_b).status_code == 404  # A's section id -> 404 in B
    # no session -> 404 after stop
    client.post(f"/api/attendance/face/stop?section_id={sec}", headers=teacher)
    assert client.get(f"/api/attendance/face/status?section_id={sec}", headers=teacher).status_code == 404


def test_face_mode_service_down_is_503(client, admin, teacher):
    vision._transport = httpx.MockTransport(FakeVision([], down=True))
    r = client.post("/api/attendance/face/start", headers=teacher, json={"section_id": section_id(client, admin)})
    assert r.status_code == 503
