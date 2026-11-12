"""Periods, timetable grid (admin builds), teacher image/text upload, personal teacher timetable."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import files
from ..db import get_db
from ..deps import child_ids, current_user, parent_of, require_roles, student_of, teacher_of, tenant_id
from ..models import Period, Role, Section, Student, Subject, Teacher, TeacherAssignment, TimetableEntry, TimetableUpload, User
from ..schemas_p2 import EntryIn, EntryOut, PeriodIn, PeriodOut, PeriodPatch, TimetableOut, UploadOut
from .people import teacher_section_ids
from .structure import get_or_404

router = APIRouter(tags=["timetable"])
admin_only = require_roles(Role.admin)
MAX_TEXT = 8000


# ------------------------------------------------------------------ periods
@router.get("/periods", response_model=list[PeriodOut])
def list_periods(_: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return db.scalars(select(Period).where(Period.school_id == sid).order_by(Period.number)).all()


@router.post("/periods", response_model=PeriodOut, status_code=201)
def create_period(body: PeriodIn, admin: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = Period(school_id=sid, created_by=admin.id, **body.model_dump())
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Period number already exists")
    return p


@router.patch("/periods/{pid}", response_model=PeriodOut)
def patch_period(pid: int, body: PeriodPatch, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = get_or_404(db, Period, pid, sid)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    if p.end_time <= p.start_time:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "end_time must be after start_time")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Period number already exists")
    return p


@router.delete("/periods/{pid}", status_code=204)
def delete_period(pid: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = get_or_404(db, Period, pid, sid)
    if db.scalar(select(TimetableEntry.id).where(TimetableEntry.school_id == sid, TimetableEntry.period_id == pid).limit(1)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Period is used in a timetable")
    db.delete(p)
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ access
def _can_view_section(db: Session, user: User, sid: int, section_id: int) -> None:
    if user.role in (Role.admin.value, Role.teacher.value):
        return  # staff can see any section's timetable
    if user.role == Role.student.value and (me := student_of(db, user)) and me.section_id == section_id:
        return
    if user.role == Role.parent.value:
        kids = child_ids(db, user)
        if kids and db.scalar(select(Student.id).where(Student.id.in_(kids), Student.section_id == section_id).limit(1)):
            return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this timetable")


def _can_upload(db: Session, user: User, section_id: int) -> None:
    if user.role == Role.admin.value:
        return
    if user.role == Role.teacher.value and section_id in teacher_section_ids(db, user):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the section's teachers or admin can upload")


# ------------------------------------------------------------------ grid
@router.get("/timetable/sections/{section_id}", response_model=TimetableOut)
def section_timetable(section_id: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    get_or_404(db, Section, section_id, sid)
    _can_view_section(db, user, sid, section_id)
    entries = db.scalars(select(TimetableEntry).where(TimetableEntry.school_id == sid, TimetableEntry.section_id == section_id)).all()
    ups = db.scalars(
        select(TimetableUpload).where(TimetableUpload.school_id == sid, TimetableUpload.section_id == section_id)
        .order_by(TimetableUpload.id.desc())
    ).all()  # fmt: skip
    return TimetableOut(section_id=section_id, entries=entries, uploads=ups)


@router.put("/timetable/entries", response_model=EntryOut)
def upsert_entry(body: EntryIn, admin: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    get_or_404(db, Section, body.section_id, sid)
    get_or_404(db, Period, body.period_id, sid)
    get_or_404(db, Subject, body.subject_id, sid)
    if body.teacher_id is not None:
        get_or_404(db, Teacher, body.teacher_id, sid)
        if not db.scalar(select(TeacherAssignment.id).where(
            TeacherAssignment.school_id == sid, TeacherAssignment.teacher_id == body.teacher_id,
            TeacherAssignment.section_id == body.section_id, TeacherAssignment.subject_id == body.subject_id,
        )):  # fmt: skip
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Teacher is not assigned to this subject in this section")
        clash = db.scalar(select(TimetableEntry).where(
            TimetableEntry.school_id == sid, TimetableEntry.teacher_id == body.teacher_id, TimetableEntry.day == body.day,
            TimetableEntry.period_id == body.period_id, TimetableEntry.section_id != body.section_id,
        ))  # fmt: skip
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, "Teacher already has another class in that period")
    e = db.scalar(select(TimetableEntry).where(
        TimetableEntry.school_id == sid, TimetableEntry.section_id == body.section_id, TimetableEntry.day == body.day,
        TimetableEntry.period_id == body.period_id,
    ))  # fmt: skip
    if e:
        e.subject_id, e.teacher_id, e.room = body.subject_id, body.teacher_id, body.room
    else:
        e = TimetableEntry(school_id=sid, created_by=admin.id, **body.model_dump())
        db.add(e)
    db.commit()
    return e


@router.delete("/timetable/entries/{eid}", status_code=204)
def delete_entry(eid: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    db.delete(get_or_404(db, TimetableEntry, eid, sid))
    db.commit()
    return Response(status_code=204)


@router.get("/timetable/me", response_model=list[EntryOut])
def my_timetable(user: User = Depends(require_roles(Role.teacher)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    t = teacher_of(db, user)
    if not t:
        return []
    return db.scalars(select(TimetableEntry).where(TimetableEntry.school_id == sid, TimetableEntry.teacher_id == t.id)).all()


# ------------------------------------------------------------------ uploads (image or text)
@router.post("/timetable/uploads", response_model=UploadOut, status_code=201)
def upload_timetable(
    section_id: int = Form(...), text: str = Form(""), file: UploadFile | None = File(None),
    user: User = Depends(require_roles(Role.admin, Role.teacher)), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    get_or_404(db, Section, section_id, sid)
    _can_upload(db, user, section_id)
    text = text.strip()
    if bool(file and file.filename) == bool(text):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Send either an image or text")
    if len(text) > MAX_TEXT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Text too long")
    up = TimetableUpload(school_id=sid, section_id=section_id, uploaded_by=user.id, created_by=user.id, kind="text", text=text)
    if file and file.filename:
        up.kind = "image"
        up.file_path, up.content_type, up.original_name = files.save_upload(sid, "timetable", file, files.IMAGE)
    db.add(up)
    db.commit()
    return up


@router.get("/timetable/uploads/{uid}/file")
def upload_file(uid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    up = get_or_404(db, TimetableUpload, uid, sid)
    _can_view_section(db, user, sid, up.section_id)
    if up.kind != "image":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No file")
    return files.serve(sid, up.file_path, up.content_type, up.original_name)


@router.delete("/timetable/uploads/{uid}", status_code=204)
def delete_upload(uid: int, user: User = Depends(require_roles(Role.admin, Role.teacher)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    up = get_or_404(db, TimetableUpload, uid, sid)
    if user.role == Role.teacher.value and up.uploaded_by != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the uploader or admin can delete")
    path = up.file_path
    db.delete(up)
    db.commit()
    files.remove(path)
    return Response(status_code=204)
