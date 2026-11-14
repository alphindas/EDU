"""Exams: Mock (practice) vs Main (graded). Teacher creates for a section+subject they teach, uploads paper / answer key,
enters marks, publishes; students and parents see marks only after publish. Admin sees everything, can unpublish."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import files
from ..assess import assert_assigned, pct, section_students
from ..db import get_db
from ..deps import child_ids, current_user, require_roles, student_of, teacher_of, tenant_id
from ..models import Exam, ExamPaper, Mark, Role, Section, Student, Subject, User
from ..notify import notify, parent_user_ids, student_user_id
from ..schemas_p3 import ExamIn, ExamOut, ExamPatch, ExamStats, MarkRow, MarksIn, MarksSheet, MyResult
from .structure import get_or_404

router = APIRouter(prefix="/exams", tags=["exams"])
teacher_only = require_roles(Role.teacher)
staff = require_roles(Role.admin, Role.teacher)
ATTACH = {**files.IMAGE, **files.DOC}


def _owner_or_admin(db: Session, user: User, e: Exam) -> None:
    if user.role == Role.admin.value:
        return
    if user.role == Role.teacher.value and (t := teacher_of(db, user)) and t.id == e.teacher_id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the teacher who owns this exam or admin")


def _can_view(db: Session, user: User, e: Exam) -> None:
    if user.role in (Role.admin.value, Role.teacher.value):
        return _owner_or_admin(db, user, e)
    if user.role == Role.student.value and (me := student_of(db, user)) and me.section_id == e.section_id:
        return
    if user.role == Role.parent.value:
        kids = child_ids(db, user)
        if kids and db.scalar(select(Student.id).where(Student.id.in_(kids), Student.section_id == e.section_id).limit(1)):
            return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this exam")


def _my_result(db: Session, e: Exam, student_id: int) -> MyResult | None:
    if e.status != "published":
        return None  # marks stay hidden until results are published
    m = db.scalar(select(Mark).where(Mark.exam_id == e.id, Mark.student_id == student_id))
    if not m:
        return None
    p = pct(m.marks, e.max_marks)
    return MyResult(marks=m.marks, absent=m.absent, percentage=p, passed=None if m.marks is None else m.marks >= e.pass_marks, remarks=m.remarks)


def _out(db: Session, e: Exam, viewer: Student | None = None, staff_view: bool = False) -> ExamOut:
    o = ExamOut.model_validate(e)
    kinds = set(db.scalars(select(ExamPaper.kind).where(ExamPaper.exam_id == e.id)))
    o.has_paper = "paper" in kinds
    if staff_view:
        o.has_key = "key" in kinds
        o.entered_count = db.scalar(select(func.count()).select_from(Mark).where(
            Mark.exam_id == e.id, (Mark.marks.is_not(None)) | (Mark.absent.is_(True)))) or 0  # fmt: skip
        o.total_students = len(section_students(db, e.school_id, e.section_id))
    if viewer:
        o.my_result = _my_result(db, e, viewer.id)
    return o


# ------------------------------------------------------------------ create / edit / delete
@router.post("", response_model=ExamOut, status_code=201)
def create_exam(body: ExamIn, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    get_or_404(db, Section, body.section_id, sid)
    get_or_404(db, Subject, body.subject_id, sid)
    t = assert_assigned(db, sid, teacher_of(db, user), body.section_id, body.subject_id)
    e = Exam(school_id=sid, created_by=user.id, teacher_id=t.id, **body.model_dump())
    db.add(e)
    db.commit()
    return _out(db, e, staff_view=True)


@router.patch("/{eid}", response_model=ExamOut)
def update_exam(eid: int, body: ExamPatch, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    e = get_or_404(db, Exam, eid, sid)
    _owner_or_admin(db, user, e)
    if e.status == "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Unpublish the results before editing the exam")
    data = body.model_dump(exclude_none=True)
    new_max = data.get("max_marks", e.max_marks)
    if data.get("pass_marks", e.pass_marks) > new_max:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "pass_marks cannot exceed max_marks")
    if "max_marks" in data and db.scalar(select(Mark.id).where(Mark.exam_id == eid, Mark.marks > new_max).limit(1)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Some entered marks are above the new maximum")
    for k, v in data.items():
        setattr(e, k, v)
    db.commit()
    return _out(db, e, staff_view=True)


@router.delete("/{eid}", status_code=204)
def delete_exam(eid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    e = get_or_404(db, Exam, eid, sid)
    _owner_or_admin(db, user, e)
    paths = []
    for child in (*db.scalars(select(Mark).where(Mark.exam_id == eid)), *db.scalars(select(ExamPaper).where(ExamPaper.exam_id == eid))):
        if isinstance(child, ExamPaper):
            paths.append(child.file_path)
        db.delete(child)
    db.flush()
    db.delete(e)
    db.commit()
    for p in paths:
        files.remove(p)
    return Response(status_code=204)


# ------------------------------------------------------------------ listing
@router.get("", response_model=list[ExamOut])
def list_exams(
    section_id: int | None = None, subject_id: int | None = None, kind: str | None = Query(None, pattern="^(mock|main)$"),
    child_id: int | None = None, limit: int = Query(100, ge=1, le=200),
    user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    q = select(Exam).where(Exam.school_id == sid)
    viewer: Student | None = None
    if user.role == Role.teacher.value:
        t = teacher_of(db, user)
        q = q.where(Exam.teacher_id == (t.id if t else -1))
    elif user.role == Role.student.value:
        viewer = student_of(db, user)
        q = q.where(Exam.section_id == (viewer.section_id if viewer else -1))
    elif user.role == Role.parent.value:
        if child_id is None or child_id not in child_ids(db, user):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "child_id of one of your children is required")
        viewer = get_or_404(db, Student, child_id, sid)
        q = q.where(Exam.section_id == viewer.section_id)
    elif user.role != Role.admin.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
    if section_id is not None and viewer is None:
        q = q.where(Exam.section_id == section_id)
    if subject_id is not None:
        q = q.where(Exam.subject_id == subject_id)
    if kind:
        q = q.where(Exam.kind == kind)
    rows = db.scalars(q.order_by(Exam.exam_date.desc(), Exam.id.desc()).limit(limit)).all()
    return [_out(db, e, viewer, staff_view=viewer is None) for e in rows]


@router.get("/{eid}", response_model=ExamOut)
def get_exam(eid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    e = get_or_404(db, Exam, eid, sid)
    _can_view(db, user, e)
    viewer = student_of(db, user) if user.role == Role.student.value else None
    return _out(db, e, viewer, staff_view=user.role in (Role.admin.value, Role.teacher.value))


# ------------------------------------------------------------------ paper + answer key
@router.post("/{eid}/papers", response_model=ExamOut)
def upload_paper(
    eid: int, kind: str = Form(..., pattern="^(paper|key)$"), file: UploadFile = File(...),
    user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    e = get_or_404(db, Exam, eid, sid)
    _owner_or_admin(db, user, e)
    rel, ctype, name = files.save_upload(sid, "exam-papers", file, ATTACH)
    row = db.scalar(select(ExamPaper).where(ExamPaper.exam_id == eid, ExamPaper.kind == kind))
    old = row.file_path if row else ""
    if not row:
        row = ExamPaper(school_id=sid, created_by=user.id, exam_id=eid, kind=kind)
        db.add(row)
    row.file_path, row.content_type, row.original_name = rel, ctype, name
    db.commit()
    files.remove(old)
    return _out(db, e, staff_view=True)


@router.get("/{eid}/papers/{kind}")
def get_paper(eid: int, kind: str, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if kind not in ("paper", "key"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    e = get_or_404(db, Exam, eid, sid)
    _can_view(db, user, e)
    if kind == "key" and user.role not in (Role.admin.value, Role.teacher.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The answer key is for staff only")
    row = db.scalar(select(ExamPaper).where(ExamPaper.exam_id == eid, ExamPaper.kind == kind))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return files.serve(sid, row.file_path, row.content_type, row.original_name)


# ------------------------------------------------------------------ marks
def _sheet(db: Session, sid: int, e: Exam) -> MarksSheet:
    marks = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.exam_id == e.id))}
    rows = []
    for s in section_students(db, sid, e.section_id):
        m = marks.get(s.id)
        rows.append(MarkRow(student_id=s.id, admission_no=s.admission_no, full_name=s.user.full_name, roll_no=s.roll_no,
                            marks=m.marks if m else None, absent=m.absent if m else False, remarks=m.remarks if m else "",
                            percentage=pct(m.marks, e.max_marks) if m else None))  # fmt: skip
    scored = [r.marks for r in rows if r.marks is not None and not r.absent]
    stats = ExamStats(
        entered=sum(1 for r in rows if r.marks is not None or r.absent), absent=sum(1 for r in rows if r.absent),
        average=round(sum(scored) / len(scored), 2) if scored else None, highest=max(scored) if scored else None,
        lowest=min(scored) if scored else None, passed=sum(1 for x in scored if x >= e.pass_marks),
        failed=sum(1 for x in scored if x < e.pass_marks),
    )  # fmt: skip
    return MarksSheet(exam=_out(db, e, staff_view=True), rows=rows, stats=stats)


@router.get("/{eid}/marks", response_model=MarksSheet)
def get_marks(eid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    e = get_or_404(db, Exam, eid, sid)
    _owner_or_admin(db, user, e)
    return _sheet(db, sid, e)


@router.put("/{eid}/marks", response_model=MarksSheet)
def put_marks(eid: int, body: MarksIn, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    e = get_or_404(db, Exam, eid, sid)
    _owner_or_admin(db, user, e)
    if e.status == "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Results are published; unpublish before changing marks")
    valid = {s.id for s in section_students(db, sid, e.section_id)}
    for r in body.rows:
        if r.student_id not in valid:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Student {r.student_id} is not in this exam's section")
        if r.marks is not None and r.marks > e.max_marks:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Marks cannot exceed {e.max_marks:g}")
    existing = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.exam_id == eid))}
    for r in body.rows:
        m = existing.get(r.student_id)
        if not m:
            m = existing[r.student_id] = Mark(school_id=sid, created_by=user.id, exam_id=eid, student_id=r.student_id)
            db.add(m)
        m.absent = r.absent
        m.marks = None if r.absent else r.marks  # an absent student has no score
        m.remarks = r.remarks
    db.commit()
    return _sheet(db, sid, e)


# ------------------------------------------------------------------ publish results
@router.post("/{eid}/publish", response_model=ExamOut)
def publish(eid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    e = get_or_404(db, Exam, eid, sid)
    _owner_or_admin(db, user, e)
    if e.status == "published":
        return _out(db, e, staff_view=True)
    sheet = _sheet(db, sid, e)
    missing = len(sheet.rows) - sheet.stats.entered
    if not sheet.rows or missing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Enter marks (or mark absent) for all students first; {missing} missing")
    e.status, e.published_at = "published", datetime.now(timezone.utc)
    sub = db.scalar(select(Subject.name).where(Subject.id == e.subject_id)) or ""
    for r in sheet.rows:
        notify(db, sid, [student_user_id(db, r.student_id), *parent_user_ids(db, r.student_id)], "exam", "notif.results_published",
               {"name": r.full_name, "exam": e.name, "subject": sub}, "report-card")  # fmt: skip
    db.commit()
    return _out(db, e, staff_view=True)


@router.post("/{eid}/unpublish", response_model=ExamOut)
def unpublish(eid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    e = get_or_404(db, Exam, eid, sid)
    _owner_or_admin(db, user, e)
    e.status, e.published_at = "draft", None
    db.commit()
    return _out(db, e, staff_view=True)
