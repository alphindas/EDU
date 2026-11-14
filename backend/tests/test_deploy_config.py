"""Deployment config: plain env names, CORS for Cloudflare Pages, optional demo seeding."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import app


def test_plain_env_names_and_cors_list(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setenv("SECRET_KEY", "s" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://a.pages.dev/, https://b.example.com")
    s = Settings(_env_file=None)
    assert s.database_url == "sqlite:///./x.db" and s.secret_key == "s" * 40
    assert s.cors_origins == ["https://a.pages.dev", "https://b.example.com"]


def test_defaults_safe_for_local_dev(monkeypatch):
    for k in ("DATABASE_URL", "SECRET_KEY", "CORS_ORIGINS", "SEED_DEMO"):
        monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=None)
    assert s.database_url.startswith("sqlite") and "http://localhost:5173" in s.cors_origins and s.seed_demo is False


def test_cors_allows_pages_dev_only():
    c = TestClient(app)
    def pre(origin):
        return c.options("/api/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                     "Access-Control-Request-Headers": "content-type,authorization"})
    ok = pre("https://edunest-abc.pages.dev")
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "https://edunest-abc.pages.dev"
    assert "access-control-allow-origin" not in pre("https://evil.example.com").headers
    assert "access-control-allow-origin" not in pre("https://pages.dev.evil.com").headers


def test_ensure_demo_data_idempotent():
    from app.db import SessionLocal
    from app.models import School
    from app.seed import ensure_demo_data
    ensure_demo_data(); ensure_demo_data()
    with SessionLocal() as db:
        assert len(db.scalars(select(School).where(School.code == "EDN01")).all()) == 1
