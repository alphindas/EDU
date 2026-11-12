from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .routers import (
    ai_chat, ai_learn, attendance, auth, exams, homework, idcard, leave, notifications, people, quizzes, reports, structure, timetable,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # swap for Alembic migrations before Postgres
    yield


app = FastAPI(title="EduNest API", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (auth.router, structure.router, people.router, attendance.router, timetable.router, homework.router,
          leave.router, idcard.router, notifications.router, quizzes.router, exams.router, reports.router, ai_chat.router, ai_learn.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
