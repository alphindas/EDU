from sqlalchemy import select

from app.models import User
from tests.conftest import login, parent_login


def test_admin_teacher_login_and_me(client):
    h = login(client, "EDN01", "admin", "admin", "admin123")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "admin" and me["school"]["code"] == "EDN01"
    h = login(client, "EDN01", "teacher", "T-001", "teacher123")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "teacher" and me["teacher_id"]


def test_bad_credentials_and_unknown_school(client):
    body = {"school_code": "EDN01", "role": "admin", "login_id": "admin", "password": "nope"}
    assert client.post("/api/auth/login", json=body).status_code == 401
    assert client.post("/api/auth/login", json={**body, "school_code": "NOPE", "password": "admin123"}).status_code == 401
    # no token
    assert client.get("/api/classes").status_code == 401


def test_passwords_are_bcrypt_hashed(client, Session):
    with Session() as db:
        for u in db.scalars(select(User).where(User.password_hash.is_not(None))):
            assert u.password_hash.startswith("$2"), u.login_id
            assert "admin123" not in u.password_hash


def test_student_first_login_forces_password_change(client):
    r = client.post("/api/auth/login", json={"school_code": "EDN01", "role": "student", "login_id": "EN-26-001",
                                             "password": "15082010"})  # DOB DDMMYYYY
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # everything but /auth/me + change-password is blocked
    blocked = client.get("/api/classes", headers=h)
    assert blocked.status_code == 403 and blocked.json()["detail"] == "password_change_required"
    assert client.get("/api/auth/me", headers=h).status_code == 200
    # short / same password rejected
    assert client.post("/api/auth/change-password", headers=h, json={"old_password": "15082010", "new_password": "short"}).status_code == 422
    assert client.post("/api/auth/change-password", headers=h, json={"old_password": "15082010", "new_password": "15082010"}).status_code == 400
    assert client.post("/api/auth/change-password", headers=h, json={"old_password": "wrong", "new_password": "NewPass#123"}).status_code == 400
    r = client.post("/api/auth/change-password", headers=h, json={"old_password": "15082010", "new_password": "NewPass#123"})
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/classes", headers=h2).status_code == 200
    # old DOB password no longer works
    assert client.post("/api/auth/login", json={"school_code": "EDN01", "role": "student", "login_id": "EN-26-001",
                                                "password": "15082010"}).status_code == 401


def test_parent_otp_flow(client):
    # parents cannot use password login
    assert client.post("/api/auth/login", json={"school_code": "EDN01", "role": "parent", "login_id": "9000000001",
                                                "password": "x"}).status_code == 400
    client.post("/api/auth/otp/request", json={"school_code": "EDN01", "mobile": "9000000001"})
    bad = client.post("/api/auth/otp/verify", json={"school_code": "EDN01", "mobile": "9000000001", "code": "111111"})
    assert bad.status_code == 401
    h, tok = parent_login(client, "EDN01", "9000000001")
    assert tok["user"]["role"] == "parent" and tok["must_change_password"] is False
    kids = client.get("/api/me/children", headers=h).json()
    assert {k["admission_no"] for k in kids} == {"EN-26-001", "EN-26-009"}  # one login, two children
    # OTP is single-use
    again = client.post("/api/auth/otp/verify", json={"school_code": "EDN01", "mobile": "9000000001", "code": "000000"})
    assert again.status_code == 401


def test_otp_unregistered_mobile_gives_no_signal_and_cannot_verify(client):
    r = client.post("/api/auth/otp/request", json={"school_code": "EDN01", "mobile": "1234567890"})
    assert r.status_code == 200 and r.json()["sent"] is True
    v = client.post("/api/auth/otp/verify", json={"school_code": "EDN01", "mobile": "1234567890", "code": "000000"})
    assert v.status_code == 401


def test_otp_attempt_limit(client):
    client.post("/api/auth/otp/request", json={"school_code": "EDN01", "mobile": "9000000002"})
    for _ in range(5):
        client.post("/api/auth/otp/verify", json={"school_code": "EDN01", "mobile": "9000000002", "code": "999999"})
    r = client.post("/api/auth/otp/verify", json={"school_code": "EDN01", "mobile": "9000000002", "code": "000000"})
    assert r.status_code == 401  # locked out even with the right code


def test_refresh_token_and_wrong_token_type(client):
    r = client.post("/api/auth/login", json={"school_code": "EDN01", "role": "admin", "login_id": "admin", "password": "admin123"})
    t = r.json()
    ok = client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert ok.status_code == 200
    # an access token is not a refresh token, and vice-versa
    assert client.post("/api/auth/refresh", json={"refresh_token": t["access_token"]}).status_code == 401
    assert client.get("/api/classes", headers={"Authorization": f"Bearer {t['refresh_token']}"}).status_code == 401


def test_login_rate_limit(client):
    body = {"school_code": "EDN01", "role": "admin", "login_id": "admin", "password": "bad"}
    codes = [client.post("/api/auth/login", json=body).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_superadmin_login_without_school(client):
    r = client.post("/api/auth/login", json={"role": "superadmin", "login_id": "super", "password": "super12345"})
    assert r.status_code == 200 and r.json()["user"]["school_id"] is None


def test_every_seeded_student_can_login_with_dob_password(client):
    """Regression: seed DOBs must match the DDMMYYYY first-login password for every student, in every school."""
    from app.seed import STUDENTS

    dobs = {adm: dob.strftime("%d%m%Y") for adm, _, _, dob, *_ in STUDENTS}
    dobs["EN-26-009"] = "20052011"
    for code in ("EDN01", "OTHER"):
        for adm, pw in dobs.items():
            r = client.post("/api/auth/login", json={"school_code": code, "role": "student", "login_id": adm, "password": pw})
            assert r.status_code == 200, f"{code}/{adm}/{pw}: {r.text}"
            assert r.json()["must_change_password"] is True


def test_success_resets_failure_counter_and_message_has_wait_time(client):
    bad = {"school_code": "EDN01", "role": "admin", "login_id": "admin", "password": "bad"}
    good = {**bad, "password": "admin123"}
    for _ in range(9):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    assert client.post("/api/auth/login", json=good).status_code == 200  # success clears the counter
    for _ in range(10):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    r = client.post("/api/auth/login", json=good)
    assert r.status_code == 429 and "min" in r.json()["detail"] and "retry-after" in r.headers


def test_many_successful_logins_never_lock_out(client):
    good = {"school_code": "EDN01", "role": "admin", "login_id": "admin", "password": "admin123"}
    assert all(client.post("/api/auth/login", json=good).status_code == 200 for _ in range(25))
