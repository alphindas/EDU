"""Attendance: manual marking, face-mode bridge, history, admin summary.

  teacher : mark/correct for own sections (class teacher or subject teacher), back-dated up to N days
  admin   : view everything, correct any date
  student : own history          parent : children's history
Absent/late marks notify the student's parents (in-app) once per status change.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import vision
from ..config import get_settings
from ..db import get_db
from ..deps import current_user, require_roles, tenant_id
from ..models import AttendanceRecord, AttendanceSession, Role, Section, Student, Subject, User
from ..notify import notify, parent_user_ids
from ..schemas_p2 import (
    FaceRowOut, FaceStartIn, FaceStatusOut, FaceStopOut, HistoryItem, HistoryOut, MarkIn, RecordIn, SessionOut,
    SheetOut, SheetRow, SummaryRow,
)
from .people import _authorise_student, teacher_section_ids
from .structure import get_or_404

router = APIRouter(prefix="/attendance", tags=["attendance"])
staff = require_roles(Role.admin, Role.teacher)
teacher_only = require_roles(Role.teacher)


def _check_section(db: Session, user: User, sid: int, section_id: int) -> Section:
    sec = get_or_404(db, Section, section_id, sid)
    if user.role == Role.teacher.value and section_id not in teacher_section_ids(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your section")
    return sec


def _roster(db: Session, sid: int, section_id: int) -> list[Student]:
    return list(
        db.scalars(
            select(Student).where(Student.school_id == sid, Student.section_id == section_id, Student.deleted_at.is_(None))
            .order_by(Student.roll_no, Student.admission_no)
        )
    )


def _find_session(db: Session, sid: int, section_id: int, d: date, period: int) -> AttendanceSession | None:
    return db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.school_id == sid, AttendanceSession.section_id == section_id,
            AttendanceSession.date == d, AttendanceSession.period == period,
        )
    )


# ------------------------------------------------------------------ manual marking
@router.get("/sheet", response_model=SheetOut)
def sheet(
    section_id: int, date: date, period: int = Query(0, ge=0, le=12),
    user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    _check_section(db, user, sid, section_id)
    sess = _find_session(db, sid, section_id, date, period)
    recs = {r.student_id: r for r in sess.records} if sess else {}
    rows = [
        SheetRow(
            student_id=s.id, admission_no=s.admission_no, full_name=s.user.full_name, roll_no=s.roll_no,
            status=recs[s.id].status if s.id in recs else None, note=recs[s.id].note if s.id in recs else "",
        )
        for s in _roster(db, sid, section_id)
    ]
    return SheetOut(section_id=section_id, date=date, period=period, exists=bool(sess), source=sess.source if sess else None, rows=rows)


@router.put("/sessions", response_model=SessionOut)
def mark(body: MarkIn, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Create or overwrite the register for <section, date, period>. Idempotent."""
    _check_section(db, user, sid, body.section_id)
    today = date.today()
    if body.date > today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot mark attendance for a future date")
    if user.role == Role.teacher.value and (today - body.date).days > get_settings().teacher_backdate_days:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Too old to edit; ask the admin to correct it")
    if body.subject_id is not None:
        get_or_404(db, Subject, body.subject_id, sid)
    ids = [r.student_id for r in body.records]
    if len(set(ids)) != len(ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Duplicate student in records")
    students = {s.id: s for s in _roster(db, sid, body.section_id)}
    if not set(ids) <= set(students):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Record for a student who is not in this section")

    sess = _find_session(db, sid, body.section_id, body.date, body.period)
    if not sess:
        sess = AttendanceSession(school_id=sid, section_id=body.section_id, date=body.date, period=body.period, created_by=user.id)
        db.add(sess)
        db.flush()
    sess.subject_id, sess.marked_by, sess.source = body.subject_id, user.id, body.source
    existing = {r.student_id: r for r in sess.records}
    for r in body.records:
        prev = existing.get(r.student_id)
        if prev:
            changed = prev.status != r.status
            prev.status, prev.note, prev.confidence = r.status, r.note, r.confidence
        else:
            changed = True
            db.add(AttendanceRecord(
                school_id=sid, session_id=sess.id, student_id=r.student_id, status=r.status, note=r.note,
                confidence=r.confidence, created_by=user.id,
            ))  # fmt: skip
        if changed and r.status in ("absent", "late"):
            notify(db, sid, parent_user_ids(db, r.student_id), "attendance", f"notif.attendance_{r.status}",
                   {"name": students[r.student_id].user.full_name, "date": body.date.isoformat(), "period": body.period},
                   "attendance")  # fmt: skip
    db.commit()
    db.refresh(sess)
    return sess


# ------------------------------------------------------------------ admin / teacher summary
@router.get("/summary", response_model=list[SummaryRow])
def summary(date: date, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Per section for one day. If several periods were marked, the earliest period of the day is counted."""
    sec_q = select(Section).where(Section.school_id == sid)
    if user.role == Role.teacher.value:
        sec_q = sec_q.where(Section.id.in_(teacher_section_ids(db, user) or {-1}))
    out = []
    for sec in db.scalars(sec_q.order_by(Section.class_id, Section.name)):
        total = len(_roster(db, sid, sec.id))
        sess = db.scalar(
            select(AttendanceSession).where(
                AttendanceSession.school_id == sid, AttendanceSession.section_id == sec.id, AttendanceSession.date == date
            ).order_by(AttendanceSession.period).limit(1)
        )
        counts = {"present": 0, "absent": 0, "late": 0}
        if sess:
            for r in sess.records:
                counts[r.status] += 1
        out.append(SummaryRow(section_id=sec.id, total=total, marked=bool(sess), **counts))
    return out


# ------------------------------------------------------------------ history (student / parent / staff)
@router.get("/students/{student_id}", response_model=HistoryOut)
def history(
    student_id: int, from_: date | None = Query(None, alias="from"), to: date | None = None,
    user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    stu = get_or_404(db, Student, student_id, sid)
    _authorise_student(db, user, stu)
    to = to or date.today()
    from_ = from_ or to - timedelta(days=30)
    rows = db.execute(
        select(AttendanceSession.date, AttendanceSession.period, AttendanceRecord.status, AttendanceRecord.note)
        .join(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
        .where(AttendanceRecord.school_id == sid, AttendanceRecord.student_id == student_id,
               AttendanceSession.date >= from_, AttendanceSession.date <= to)
        .order_by(AttendanceSession.date.desc(), AttendanceSession.period)
    ).all()  # fmt: skip
    items = [HistoryItem(date=r[0], period=r[1], status=r[2], note=r[3]) for r in rows]
    n = {k: sum(1 for i in items if i.status == k) for k in ("present", "absent", "late")}
    pct = round(100 * (n["present"] + n["late"]) / len(items), 1) if items else None
    return HistoryOut(student_id=student_id, items=items, percentage=pct, **n)


# ------------------------------------------------------------------ face mode (bridge to services/vision)
def _map_rows(db: Session, sid: int, section_id: int, rows: list[dict]) -> tuple[list[FaceRowOut], int]:
    by_adm = {s.admission_no: s for s in _roster(db, sid, section_id)}
    out, unmatched = [], 0
    for r in rows:
        stu = by_adm.get(str(r.get("Register Number", "")))
        if not stu:
            unmatched += 1
            continue
        st = "late" if str(r.get("Status", "")).lower() == "late" else "present"
        out.append(FaceRowOut(student_id=stu.id, admission_no=stu.admission_no, full_name=stu.user.full_name, status=st,
                              confidence=r.get("Confidence"), time=r.get("Time")))  # fmt: skip
    return out, unmatched


@router.post("/face/start", response_model=FaceStatusOut)
def face_start(body: FaceStartIn, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    _check_section(db, user, sid, body.section_id)
    st = vision.start(sid, body.section_id, user.id, body.period)
    detected, unmatched = _map_rows(db, sid, body.section_id, st.get("present", []))
    return FaceStatusOut(running=True, demo=bool(st.get("demo")), period=body.period, section_id=body.section_id,
                         total=len(_roster(db, sid, body.section_id)), detected=detected, unmatched=unmatched)  # fmt: skip


@router.get("/face/status", response_model=FaceStatusOut)
def face_status(section_id: int, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    _check_section(db, user, sid, section_id)
    o, st = vision.status_rows(sid, section_id)
    detected, unmatched = _map_rows(db, sid, section_id, st.get("present", []))
    return FaceStatusOut(running=bool(st.get("running")), demo=bool(st.get("demo")), period=o["period"], section_id=section_id,
                         total=len(_roster(db, sid, section_id)), detected=detected, unmatched=unmatched)  # fmt: skip


@router.post("/face/stop", response_model=FaceStopOut)
def face_stop(section_id: int, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Stops the camera session and returns a PROPOSED register (detected -> present/late, everyone else absent).
    The teacher reviews/corrects it, then saves with PUT /attendance/sessions (source=face)."""
    _check_section(db, user, sid, section_id)
    o, rows = vision.stop(sid, section_id)
    detected, unmatched = _map_rows(db, sid, section_id, rows)
    seen = {d.student_id: d for d in detected}
    proposal = [
        RecordIn(student_id=s.id, status=seen[s.id].status if s.id in seen else "absent",
                 confidence=seen[s.id].confidence if s.id in seen else None)
        for s in _roster(db, sid, section_id)
    ]  # fmt: skip
    return FaceStopOut(section_id=section_id, period=o["period"], proposal=proposal, unmatched=unmatched)
