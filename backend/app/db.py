"""Database engine/session + the tenant guard.

Tenant isolation is enforced in two layers:
  1. Every route filters by the caller's school_id (explicit, readable).
  2. A session-level ORM hook (`_tenant_filter`) appends `school_id = :sid` to every
     SELECT/UPDATE/DELETE touching a TenantMixin table whenever `session.info["school_id"]`
     is set. Even a route that forgets the explicit filter cannot read another school's rows.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, with_loader_criteria

from .config import get_settings

_settings = get_settings()
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, connect_args=_connect_args)

if _settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):  # enforce FKs in SQLite
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "do_orm_execute")
def _tenant_filter(state):
    sid = state.session.info.get("school_id")
    if sid is None or not (state.is_select or state.is_update or state.is_delete):
        return
    from .models import TenantMixin  # local import: models import Base from here

    state.statement = state.statement.options(
        with_loader_criteria(TenantMixin, lambda cls: cls.school_id == sid, include_aliases=True)
    )


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
