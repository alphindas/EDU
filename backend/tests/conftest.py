import io
import os
import tempfile

os.environ["EDUNEST_BCRYPT_ROUNDS"] = "4"  # fast hashing in tests (must precede app imports)
os.environ["EDUNEST_REQUIRE_AI_CONSENT"] = "0"  # older AI tests run without the consent gate; test_v2 switches it on
os.environ["EDUNEST_UPLOAD_DIR"] = tempfile.mkdtemp(prefix="edunest-test-uploads-")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Role, User
from app.routers.auth import reset_rate_limits
from app.security import hash_password
from app.seed import seed_demo


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(eng, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def Session(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client(Session):
    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    reset_rate_limits()
    from app.routers.v2util import reset_burst

    reset_burst()
    with Session() as db:
        db.add(User(school_id=None, role=Role.superadmin.value, login_id="super", full_name="Root",
                    password_hash=hash_password("super12345")))  # fmt: skip
        seed_demo(db)  # school EDN01
        seed_demo(db, code="OTHER", name="Other School")  # school B: identical logins, separate data
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, code, role, login_id, password):
    r = client.post("/api/auth/login", json={"school_code": code, "role": role, "login_id": login_id, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "EDN01", "admin", "admin", "admin123")


@pytest.fixture()
def admin_b(client):
    return login(client, "OTHER", "admin", "admin", "admin123")


@pytest.fixture()
def teacher(client):
    return login(client, "EDN01", "teacher", "T-001", "teacher123")


def parent_login(client, code, mobile):
    assert client.post("/api/auth/otp/request", json={"school_code": code, "mobile": mobile}).status_code == 200
    r = client.post("/api/auth/otp/verify", json={"school_code": code, "mobile": mobile, "code": "000000"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def teacher_login(client, code, emp):
    return login(client, code, "teacher", emp, "teacher123")


def student_login(client, code, adm, dob_ddmmyyyy):
    """Students must change their DOB password on first login; returns headers of the post-change token."""
    r = client.post("/api/auth/login", json={"school_code": code, "role": "student", "login_id": adm, "password": dob_ddmmyyyy})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/api/auth/change-password", headers=h, json={"old_password": dob_ddmmyyyy, "new_password": "NewPass#123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def student1(client):  # Aarav Reddy, 10-A, parent 9000000001
    return student_login(client, "EDN01", "EN-26-001", "15082010")


@pytest.fixture()
def student1_b(client):
    return student_login(client, "OTHER", "EN-26-001", "15082010")


@pytest.fixture()
def parent1(client):
    return parent_login(client, "EDN01", "9000000001")[0]


@pytest.fixture()
def teacher2(client):  # T-002: class teacher of 10-B, teaches Science
    return teacher_login(client, "EDN01", "T-002")


@pytest.fixture()
def teacher_b(client):
    return teacher_login(client, "OTHER", "T-001")


def png_bytes(color=(200, 30, 30)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _vision_reset():
    from app import vision

    vision.reset()
    vision._transport = None
    yield
    vision.reset()
    vision._transport = None


def section_id(client, h, label="10-A"):
    cls = {c["id"]: c["name"] for c in client.get("/api/classes", headers=h).json()}
    for s in client.get("/api/sections", headers=h).json():
        if f"{cls[s['class_id']]}-{s['name']}" == label:
            return s["id"]
    raise KeyError(label)


def subject_id(client, h, name):
    return next(s["id"] for s in client.get("/api/subjects", headers=h).json() if s["name"] == name)


def student_ids(client, h):
    return {s["admission_no"]: s["id"] for s in client.get("/api/students?limit=200", headers=h).json()["items"]}
