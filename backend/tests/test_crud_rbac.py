from tests.conftest import login, parent_login


def ids(client, h):
    cls = {c["name"]: c["id"] for c in client.get("/api/classes", headers=h).json()}
    secs = client.get("/api/sections", headers=h).json()
    return cls, secs


def new_student(adm="EN-26-100", **kw):
    return {"admission_no": adm, "full_name": "New Kid", "dob": "2010-02-03", "parent_mobile": "9111111111",
            "parent_name": "Pat", **kw}


# ------------------------------------------------------------------ structure CRUD
def test_class_section_subject_crud(client, admin):
    r = client.post("/api/classes", headers=admin, json={"name": "8", "sort_order": 8})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.post("/api/classes", headers=admin, json={"name": "8"}).status_code == 409
    r = client.post("/api/sections", headers=admin, json={"class_id": cid, "name": "A"})
    sec = r.json()["id"]
    assert client.post("/api/sections", headers=admin, json={"class_id": cid, "name": "A"}).status_code == 409
    assert client.patch(f"/api/sections/{sec}", headers=admin, json={"name": "B"}).json()["name"] == "B"
    s = client.post("/api/subjects", headers=admin, json={"name": "Drawing"})
    assert s.status_code == 201
    assert client.delete(f"/api/subjects/{s.json()['id']}", headers=admin).status_code == 204
    assert client.delete(f"/api/sections/{sec}", headers=admin).status_code == 204
    assert client.delete(f"/api/classes/{cid}", headers=admin).status_code == 204


def test_cannot_delete_class_with_students(client, admin):
    cls, _ = ids(client, admin)
    assert client.delete(f"/api/classes/{cls['10']}", headers=admin).status_code == 409


def test_class_teacher_and_assignment(client, admin):
    cls, secs = ids(client, admin)
    t = client.post("/api/teachers", headers=admin, json={"employee_id": "T-900", "full_name": "Mr. New"}).json()
    assert t["temp_password"] and len(t["temp_password"]) >= 8
    sec = next(s for s in secs if s["class_id"] == cls["9"])
    assert client.patch(f"/api/sections/{sec['id']}", headers=admin, json={"class_teacher_id": t["id"]}).json()["class_teacher_id"] == t["id"]
    subj = client.get("/api/subjects", headers=admin).json()[0]
    a = client.post("/api/assignments", headers=admin, json={"teacher_id": t["id"], "section_id": sec["id"], "subject_id": subj["id"]})
    assert a.status_code == 201
    assert client.post("/api/assignments", headers=admin, json={"teacher_id": t["id"], "section_id": sec["id"], "subject_id": subj["id"]}).status_code == 409
    # new teacher must change the generated password on first login
    r = client.post("/api/auth/login", json={"school_code": "EDN01", "role": "teacher", "login_id": "T-900", "password": t["temp_password"]})
    assert r.json()["must_change_password"] is True
    # deleting the teacher frees the section and blocks login
    assert client.delete(f"/api/teachers/{t['id']}", headers=admin).status_code == 204
    assert client.get("/api/sections", headers=admin).json()
    assert client.post("/api/auth/login", json={"school_code": "EDN01", "role": "teacher", "login_id": "T-900", "password": t["temp_password"]}).status_code == 401


# ------------------------------------------------------------------ student + parent auto-create
def test_create_student_autocreates_parent_and_links_siblings(client, admin):
    cls, secs = ids(client, admin)
    sec = next(s for s in secs if s["class_id"] == cls["10"] and s["name"] == "B")
    body = new_student(class_id=cls["10"], section_id=sec["id"])
    r = client.post("/api/students", headers=admin, json=body)
    assert r.status_code == 201 and r.json()["temp_password"] == "03022010"
    r2 = client.post("/api/students", headers=admin, json={**body, "admission_no": "EN-26-101", "full_name": "Sibling"})
    assert r2.status_code == 201
    h, _ = parent_login(client, "EDN01", "9111111111")  # brand-new parent can OTP-login immediately
    assert len(client.get("/api/me/children", headers=h).json()) == 2
    assert client.post("/api/students", headers=admin, json=body).status_code == 409  # duplicate admission no


def test_section_must_belong_to_class(client, admin):
    cls, secs = ids(client, admin)
    sec_of_9 = next(s for s in secs if s["class_id"] == cls["9"])
    r = client.post("/api/students", headers=admin, json=new_student(class_id=cls["10"], section_id=sec_of_9["id"]))
    assert r.status_code == 422


def test_student_patch_and_soft_delete(client, admin):
    st = client.get("/api/students?q=Aarav", headers=admin).json()["items"][0]
    r = client.patch(f"/api/students/{st['id']}", headers=admin, json={"full_name": "Aarav R.", "roll_no": 5})
    assert r.json()["full_name"] == "Aarav R." and r.json()["roll_no"] == 5
    assert client.delete(f"/api/students/{st['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/students/{st['id']}", headers=admin).status_code == 404
    assert client.get("/api/students?q=Aarav", headers=admin).json()["total"] == 0
    r = client.post("/api/auth/login", json={"school_code": "EDN01", "role": "student", "login_id": "EN-26-001", "password": "15082010"})
    assert r.status_code == 401  # login disabled


def test_pagination_and_filters(client, admin):
    cls, secs = ids(client, admin)
    page = client.get("/api/students?limit=3&offset=0", headers=admin).json()
    assert page["total"] == 9 and len(page["items"]) == 3
    only9 = client.get(f"/api/students?class_id={cls['9']}", headers=admin).json()
    assert only9["total"] == 1


def test_parent_listing_shows_children(client, admin):
    page = client.get("/api/parents", headers=admin).json()
    assert page["total"] == 8
    multi = next(p for p in page["items"] if p["mobile"] == "9000000001")
    assert len(multi["children"]) == 2


def test_school_profile_and_academic_year(client, admin):
    assert client.patch("/api/school", headers=admin, json={"headmaster_name": "New HM"}).json()["headmaster_name"] == "New HM"
    y = client.post("/api/academic-years", headers=admin,
                    json={"label": "2027-28", "start_date": "2027-06-01", "end_date": "2028-04-30", "is_current": True})
    assert y.status_code == 201
    years = client.get("/api/academic-years", headers=admin).json()
    assert [y["is_current"] for y in years] == [False, True]


def test_superadmin_creates_school(client):
    r = client.post("/api/auth/login", json={"role": "superadmin", "login_id": "super", "password": "super12345"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    body = {"name": "Third", "code": "THIRD", "admin_password": "supersecret1"}
    assert client.post("/api/schools", headers=h, json=body).status_code == 201
    assert client.post("/api/schools", headers=h, json=body).status_code == 409
    assert len(client.get("/api/schools", headers=h).json()) == 3
    login(client, "THIRD", "admin", "admin", "supersecret1")
    # superadmin has no school scope, so school-scoped endpoints refuse it
    assert client.get("/api/classes", headers=h).status_code == 400


# ------------------------------------------------------------------ RBAC
def test_only_admin_can_write(client, teacher):
    assert client.post("/api/classes", headers=teacher, json={"name": "7"}).status_code == 403
    assert client.post("/api/teachers", headers=teacher, json={"employee_id": "X", "full_name": "x"}).status_code == 403
    assert client.post("/api/students", headers=teacher, json=new_student(class_id=1, section_id=1)).status_code == 403
    assert client.get("/api/parents", headers=teacher).status_code == 403
    assert client.patch("/api/school", headers=teacher, json={"name": "hacked"}).status_code == 403
    assert client.post("/api/schools", headers=teacher, json={"name": "x", "code": "XX", "admin_password": "12345678"}).status_code == 403


def student_headers(client, adm, dob):
    r = client.post("/api/auth/login", json={"school_code": "EDN01", "role": "student", "login_id": adm, "password": dob})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/api/auth/change-password", headers=h, json={"old_password": dob, "new_password": "Changed#1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_student_can_read_only_self(client, admin):
    h = student_headers(client, "EN-26-002", "22032010")
    mine = client.get("/api/auth/me", headers=h).json()["student_id"]
    assert client.get(f"/api/students/{mine}", headers=h).status_code == 200
    other = next(s for s in client.get("/api/students", headers=admin).json()["items"] if s["id"] != mine)
    assert client.get(f"/api/students/{other['id']}", headers=h).status_code == 403
    assert client.get("/api/students", headers=h).status_code == 403  # no list for students
    assert client.post("/api/classes", headers=h, json={"name": "1"}).status_code == 403
    assert client.get("/api/classes", headers=h).status_code == 200  # shared reference data is readable


def test_parent_can_read_only_own_children(client, admin):
    h, _ = parent_login(client, "EDN01", "9000000002")
    mine = client.get("/api/me/children", headers=h).json()
    assert len(mine) == 1
    assert client.get(f"/api/students/{mine[0]['id']}", headers=h).status_code == 200
    other = next(s for s in client.get("/api/students", headers=admin).json()["items"] if s["id"] != mine[0]["id"])
    assert client.get(f"/api/students/{other['id']}", headers=h).status_code == 403
    assert client.get("/api/students", headers=h).json()["total"] == 1
    assert client.get("/api/teachers", headers=h).status_code == 403
    assert client.get("/api/parents", headers=h).status_code == 403


def test_teacher_sees_only_own_sections(client, admin):
    h = login(client, "EDN01", "teacher", "T-003", "teacher123")  # English: 10-A + 9-A (class teacher of 9-A)
    h2 = login(client, "EDN01", "teacher", "T-002", "teacher123")  # Science 10-A, 10-B
    assert client.get("/api/students", headers=h).json()["total"] == 9
    # T-002 teaches 10-A and 10-B only -> not Ishaan in 9-A
    names = [s["full_name"] for s in client.get("/api/students", headers=h2).json()["items"]]
    assert "Ishaan Reddy" not in names and len(names) == 8
    ishaan = next(s for s in client.get("/api/students", headers=admin).json()["items"] if s["full_name"] == "Ishaan Reddy")
    assert client.get(f"/api/students/{ishaan['id']}", headers=h2).status_code == 403
    assert client.get(f"/api/students/{ishaan['id']}", headers=h).status_code == 200
