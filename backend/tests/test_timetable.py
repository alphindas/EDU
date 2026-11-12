from tests.conftest import png_bytes, section_id, subject_id


def periods(client, h):
    return {p["number"]: p["id"] for p in client.get("/api/periods", headers=h).json()}


def test_period_crud_and_validation(client, admin, teacher):
    assert len(client.get("/api/periods", headers=teacher).json()) == 8  # any school user may read
    assert client.post("/api/periods", headers=teacher, json={"number": 9, "start_time": "15:00", "end_time": "15:45"}).status_code == 403
    assert client.post("/api/periods", headers=admin, json={"number": 1, "start_time": "15:00", "end_time": "15:45"}).status_code == 409
    assert client.post("/api/periods", headers=admin, json={"number": 9, "start_time": "15:45", "end_time": "15:00"}).status_code == 422
    r = client.post("/api/periods", headers=admin, json={"number": 9, "label": "Zero", "start_time": "15:00", "end_time": "15:45"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.patch(f"/api/periods/{pid}", headers=admin, json={"end_time": "14:00"}).status_code == 422
    assert client.patch(f"/api/periods/{pid}", headers=admin, json={"label": "Remedial"}).json()["label"] == "Remedial"
    assert client.delete(f"/api/periods/{pid}", headers=admin).status_code == 204
    used = periods(client, admin)[1]  # period 1 is used by the seeded 10-A timetable
    assert client.delete(f"/api/periods/{used}", headers=admin).status_code == 409


def test_entries_admin_builds_with_validation(client, admin, teacher, student1, parent1):
    sec10a, sec10b = section_id(client, admin), section_id(client, admin, "10-B")
    maths, sci = subject_id(client, admin, "Mathematics"), subject_id(client, admin, "Science")
    p = periods(client, admin)
    teachers = {t["employee_id"]: t["id"] for t in client.get("/api/teachers", headers=admin).json()["items"]}
    # seed: 10-A Monday has Maths/T-001 in period 1, Science/T-002 in period 2, English/T-003 in period 4 -> period 4 is free for T-001
    body = {"section_id": sec10b, "day": 0, "period_id": p[4], "subject_id": maths, "teacher_id": teachers["T-001"], "room": "B-1"}
    assert client.put("/api/timetable/entries", headers=teacher, json=body).status_code == 403
    assert client.put("/api/timetable/entries", headers=admin, json=body).status_code == 200
    # upsert of the same cell updates in place
    assert client.put("/api/timetable/entries", headers=admin, json={**body, "room": "B-2"}).json()["room"] == "B-2"
    n = len(client.get(f"/api/timetable/sections/{sec10b}", headers=admin).json()["entries"])
    assert n == 1
    # teacher double-booking (T-001 already has 10-A Maths Monday period 1)
    clash = client.put("/api/timetable/entries", headers=admin, json={**body, "period_id": p[1]})
    assert clash.status_code == 409 and "another class" in clash.json()["detail"]
    # teacher not assigned to that subject in that section
    assert client.put("/api/timetable/entries", headers=admin, json={**body, "day": 1, "subject_id": sci}).status_code == 422
    # bad day / unknown period
    assert client.put("/api/timetable/entries", headers=admin, json={**body, "day": 7}).status_code == 422
    assert client.put("/api/timetable/entries", headers=admin, json={**body, "period_id": 999999}).status_code == 404
    # a slot with no teacher is fine
    assert client.put("/api/timetable/entries", headers=admin, json={**body, "day": 2, "teacher_id": None}).status_code == 200
    # views
    assert len(client.get(f"/api/timetable/sections/{sec10a}", headers=student1).json()["entries"]) == 36
    assert client.get(f"/api/timetable/sections/{sec10a}", headers=parent1).status_code == 200
    assert client.get(f"/api/timetable/sections/{sec10b}", headers=student1).status_code == 403  # other section
    assert client.get(f"/api/timetable/sections/{sec10b}", headers=parent1).status_code == 403  # no child there
    mine = client.get("/api/timetable/me", headers=teacher).json()
    assert mine and all(e["teacher_id"] == teachers["T-001"] for e in mine)
    # delete
    eid = client.get(f"/api/timetable/sections/{sec10b}", headers=admin).json()["entries"][0]["id"]
    assert client.delete(f"/api/timetable/entries/{eid}", headers=teacher).status_code == 403
    assert client.delete(f"/api/timetable/entries/{eid}", headers=admin).status_code == 204


def test_upload_image_and_text(client, admin, teacher, teacher2, student1, parent1):
    sec = section_id(client, admin)
    # text
    r = client.post("/api/timetable/uploads", headers=teacher, data={"section_id": sec, "text": "Mon: Maths, Sci\nTue: Eng"})
    assert r.status_code == 201 and r.json()["kind"] == "text"
    # image
    r = client.post("/api/timetable/uploads", headers=teacher, data={"section_id": sec}, files={"file": ("tt.png", png_bytes(), "image/png")})
    assert r.status_code == 201 and r.json()["kind"] == "image"
    uid = r.json()["id"]
    ups = client.get(f"/api/timetable/sections/{sec}", headers=student1).json()["uploads"]
    assert [u["kind"] for u in ups] == ["image", "text"]  # newest first
    got = client.get(f"/api/timetable/uploads/{uid}/file", headers=student1)
    assert got.status_code == 200 and got.headers["content-type"] == "image/png" and got.content == png_bytes()
    assert got.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/api/timetable/uploads/{uid}/file").status_code == 401  # auth required
    # validation: neither/both, non-image bytes pretending to be png, html, oversize
    assert client.post("/api/timetable/uploads", headers=teacher, data={"section_id": sec}).status_code == 422
    assert client.post("/api/timetable/uploads", headers=teacher, data={"section_id": sec, "text": "x"}, files={"file": ("a.png", png_bytes(), "image/png")}).status_code == 422
    assert client.post("/api/timetable/uploads", headers=teacher, data={"section_id": sec}, files={"file": ("a.png", b"not an image", "image/png")}).status_code == 415
    assert client.post("/api/timetable/uploads", headers=teacher, data={"section_id": sec}, files={"file": ("a.png", b"<html><script>1</script></html>", "image/png")}).status_code == 415
    assert client.post("/api/timetable/uploads", headers=teacher, data={"section_id": sec}, files={"file": ("a.pdf", b"%PDF-1.4 x", "application/pdf")}).status_code == 415  # timetable = image only
    # who may upload / delete
    assert client.post("/api/timetable/uploads", headers=student1, data={"section_id": sec, "text": "x"}).status_code == 403
    assert client.post("/api/timetable/uploads", headers=parent1, data={"section_id": sec, "text": "x"}).status_code == 403
    assert client.post("/api/timetable/uploads", headers=teacher2, data={"section_id": section_id(client, admin, "9-A"), "text": "x"}).status_code == 403
    assert client.delete(f"/api/timetable/uploads/{uid}", headers=teacher2).status_code == 403  # not the uploader
    assert client.delete(f"/api/timetable/uploads/{uid}", headers=teacher).status_code == 204
    assert client.get(f"/api/timetable/uploads/{uid}/file", headers=student1).status_code == 404


def test_upload_size_limit(client, admin, teacher, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    sec = section_id(client, admin)
    r = client.post("/api/timetable/uploads", headers=teacher, data={"section_id": sec}, files={"file": ("a.png", png_bytes(), "image/png")})
    assert r.status_code == 413
