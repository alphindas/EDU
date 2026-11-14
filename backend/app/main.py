import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import models_v2  # noqa: F401  (registers EduNest 2.0 tables with Base.metadata)
from .config import get_settings
from .db import Base, engine, get_db
from .routers import (
    ai_chat, ai_learn, attendance, auth, chitti, coach, community, content, exams, game, homework, idcard, insights, leave, notifications,
    people, quizzes, reports, structure, timetable, transport, ws,
)  # fmt: skip
from .security import decode_token


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # creates any missing tables (incl. 2.0 ones) on an existing DB; see migrations/ for Postgres
    ws.hub.bind(asyncio.get_running_loop())
    if get_settings().seed_demo:
        from .seed import ensure_demo_data

        ensure_demo_data()
    yield


app = FastAPI(title="EduNest 2.0 API", version="2.0.0", lifespan=lifespan,
              description="AI-powered smart school portal: 4 role portals + the shared CHITTI 2.0 engine.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_origin_regex=get_settings().cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDITED = {"POST", "PUT", "PATCH", "DELETE"}
SKIP_AUDIT = ("/api/auth/refresh", "/api/notifications")


@app.middleware("http")
async def audit(request: Request, call_next):
    """Audit log for every mutating API call: who, what path, result. Bodies are never stored (may hold personal data)."""
    response = await call_next(request)
    path = request.url.path
    if request.method in AUDITED and path.startswith("/api/") and not path.startswith(SKIP_AUDIT):
        auth_h = request.headers.get("authorization", "")
        uid = decode_token(auth_h[7:], "access") if auth_h.lower().startswith("bearer ") else None
        await asyncio.to_thread(_write_audit, uid, request.method, path, response.status_code)
    return response


def _write_audit(uid, method, path, code):
    from sqlalchemy import select

    from .models import User
    from .models_v2 import AuditLog

    gen = app.dependency_overrides.get(get_db, get_db)()  # honours the test DB override
    db = next(gen)
    try:
        u = db.scalar(select(User).where(User.id == uid)) if uid else None
        if u is None and path.startswith("/api/auth/"):
            return  # anonymous login attempts are covered by the login limiter, not the audit log
        db.add(AuditLog(school_id=u.school_id if u else None, user_id=uid, role=u.role if u else "", action=method, path=path[:300], status_code=code))
        db.commit()
    except Exception:  # auditing must never break a request
        db.rollback()
    finally:
        gen.close()


for r in (auth.router, structure.router, people.router, attendance.router, timetable.router, homework.router, leave.router,
          idcard.router, notifications.router, quizzes.router, exams.router, reports.router, ai_chat.router, ai_learn.router,
          chitti.router, game.router, coach.router, content.router, community.router, transport.router, insights.router, ws.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    from . import providers

    return {"ok": True, "version": "2.0.0", "ai_provider": providers.provider_name()}
