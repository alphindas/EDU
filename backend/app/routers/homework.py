"""Homework: teacher posts (for a section+subject they are assigned), student submits (text/photo/PDF/voice),
teacher reviews, parent sees status, admin sees completion counts."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import files
from ..db import get_db
from ..deps import child_ids, current_user, require_roles, student_of, teacher_of, tenant_id
from ..models import Homework, HomeworkSubmission, Role, Section, Student, Subject, TeacherAssignment, User
from ..notify import notify, parent_user_ids, student_user_id
from ..schemas_p2 import HomeworkOut, ReviewIn, SubmissionOut, SubmissionRow
from .structure import get_or_404

router = APIRouter(prefix="/homework", tags=["homework"])
teacher_only = require_roles(Role.teacher)
student_only = require_roles(Role.student)
ATTACH = {**files.IMAGE, **files.DOC}
SUBMIT = {**files.IMAGE, **files.DOC, **files.AUDIO}


def _count_students(db: Session, sid: int, section_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Student).where(
        Student.school_id == sid, Student.section_id == section_id, Student.deleted_at.is_(None))) or 0  # fmt: skip


def _out(db: Session, sid: int, h: Homework, my: HomeworkSubmission | None = None, with_counts: bool = False) -> HomeworkOut:
    o = HomeworkOut(
        id=h.id, section_id=h.section_id, subject_id=h.subject_id, teacher_id=h.teacher_id, title=h.title,
        description=h.description, due_date=h.due_date, attachment_name=h.original_name, created_at=h.created_at,
        my_submission=SubmissionOut.model_validate(my) if my else None,
    )  # fmt: skip
    if with_counts:
        o.total_students = _count_students(db, sid, h.section_id)
        rows = db.execute(
            select(HomeworkSubmission.status, func.count()).where(HomeworkSubmission.homework_id == h.id).group_by(HomeworkSubmission.status)
        ).all()
        d = dict(rows)
        o.submitted_count = sum(d.values())
        o.reviewed_count = d.get("reviewed", 0)
    return o


def _can_view(db: Session, user: User, h: Homework) -> None:
    """Teacher: own homework; admin: all; student: own section; parent: a child's section."""
    if user.role == Role.admin.value:
        return
    if user.role == Role.teacher.value and (t := teacher_of(db, user)) and t.id == h.teacher_id:
        return
    if user.role == Role.student.value and (me := student_of(db, user)) and me.section_id == h.section_id:
        return
    if user.role == Role.parent.value:
        kids = child_ids(db, user)
        if kids and db.scalar(select(Student.id).where(Student.id.in_(kids), Student.section_id == h.section_id).limit(1)):
            return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this homework")


def _owner_or_admin(db: Session, user: User, h: Homework) -> None:
    if user.role == Role.admin.value:
        return
    if user.role == Role.teacher.value and (t := teacher_of(db, user)) and t.id == h.teacher_id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the teacher who posted it or admin")


# ------------------------------------------------------------------ teacher posts
@router.post("", response_model=HomeworkOut, status_code=201)
def create_homework(
    section_id: int = Form(...), subject_id: int = Form(...), title: str = Form(..., min_length=1, max_length=200),
    description: str = Form("", max_length=5000), due_date: date = Form(...), file: UploadFile | None = File(None),
    user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    get_or_404(db, Section, section_id, sid)
    get_or_404(db, Subject, subject_id, sid)
    t = teacher_of(db, user)
    if not t or not db.scalar(select(TeacherAssignment.id).where(
        TeacherAssignment.school_id == sid, TeacherAssignment.teacher_id == t.id,
        TeacherAssignment.section_id == section_id, TeacherAssignment.subject_id == subject_id,
    )):  # fmt: skip
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not teach this subject in this section")
    if due_date < date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Due date is in the past")
    h = Homework(school_id=sid, created_by=user.id, section_id=section_id, subject_id=subject_id, teacher_id=t.id,
                 title=title.strip(), description=description, due_date=due_date)  # fmt: skip
    if file and file.filename:
        h.file_path, h.content_type, h.original_name = files.save_upload(sid, "homework", file, ATTACH)
    db.add(h)
    db.commit()
    return _out(db, sid, h, with_counts=True)


@router.delete("/{hid}", status_code=204)
def delete_homework(hid: int, user: User = Depends(require_roles(Role.admin, Role.teacher)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    h = get_or_404(db, Homework, hid, sid)
    _owner_or_admin(db, user, h)
    paths = [h.file_path]
    for s in db.scalars(select(HomeworkSubmission).where(HomeworkSubmission.homework_id == hid)):
        paths.append(s.file_path)
        db.delete(s)
    db.flush()  # children first: no ORM relationship tells the unit of work the order
    db.delete(h)
    db.commit()
    for pth in paths:  # only after the DB commit succeeded
        files.remove(pth)
    return Response(status_code=204)


# ------------------------------------------------------------------ listing
@router.get("", response_model=list[HomeworkOut])
def list_homework(
    section_id: int | None = None, subject_id: int | None = None, child_id: int | None = None,
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    q = select(Homework).where(Homework.school_id == sid)
    viewer: Student | None = None
    if user.role == Role.teacher.value:
        t = teacher_of(db, user)
        q = q.where(Homework.teacher_id == (t.id if t else -1))
    elif user.role == Role.student.value:
        viewer = student_of(db, user)
        q = q.where(Homework.section_id == (viewer.section_id if viewer else -1))
    elif user.role == Role.parent.value:
        if child_id is None or child_id not in child_ids(db, user):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "child_id of one of your children is required")
        viewer = get_or_404(db, Student, child_id, sid)
        q = q.where(Homework.section_id == viewer.section_id)
    elif user.role != Role.admin.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
    if section_id is not None and user.role in (Role.admin.value, Role.teacher.value):
        q = q.where(Homework.section_id == section_id)
    if subject_id is not None:
        q = q.where(Homework.subject_id == subject_id)
    rows = db.scalars(q.order_by(Homework.due_date.desc(), Homework.id.desc()).limit(limit)).all()
    mine = {}
    if viewer and rows:
        mine = {
            s.homework_id: s
            for s in db.scalars(select(HomeworkSubmission).where(HomeworkSubmission.student_id == viewer.id,
                                                                  HomeworkSubmission.homework_id.in_([h.id for h in rows])))
        }  # fmt: skip
    staff = viewer is None
    return [_out(db, sid, h, mine.get(h.id), with_counts=staff) for h in rows]


@router.get("/{hid}", response_model=HomeworkOut)
def get_homework(hid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    h = get_or_404(db, Homework, hid, sid)
    _can_view(db, user, h)
    return _out(db, sid, h, with_counts=user.role in (Role.admin.value, Role.teacher.value))


@router.get("/{hid}/attachment")
def attachment(hid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    h = get_or_404(db, Homework, hid, sid)
    _can_view(db, user, h)
    return files.serve(sid, h.file_path, h.content_type, h.original_name)


# ------------------------------------------------------------------ submissions
@router.get("/{hid}/submissions", response_model=list[SubmissionRow])
def submissions(hid: int, user: User = Depends(require_roles(Role.admin, Role.teacher)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Every student in the section with their submission (or null = pending)."""
    h = get_or_404(db, Homework, hid, sid)
    _owner_or_admin(db, user, h)
    subs = {s.student_id: s for s in db.scalars(select(HomeworkSubmission).where(HomeworkSubmission.homework_id == hid))}
    studs = db.scalars(select(Student).where(Student.school_id == sid, Student.section_id == h.section_id, Student.deleted_at.is_(None))
                       .order_by(Student.roll_no, Student.admission_no)).all()  # fmt: skip
    return [
        SubmissionRow(student_id=s.id, admission_no=s.admission_no, full_name=s.user.full_name, roll_no=s.roll_no,
                      submission=SubmissionOut.model_validate(subs[s.id]) if s.id in subs else None)
        for s in studs
    ]  # fmt: skip


@router.post("/{hid}/submissions", response_model=SubmissionOut, status_code=201)
def submit(
    hid: int, text: str = Form("", max_length=10000), file: UploadFile | None = File(None),
    user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    h = get_or_404(db, Homework, hid, sid)
    me = student_of(db, user)
    if not me or me.section_id != h.section_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This homework is not for your section")
    has_file = bool(file and file.filename)
    if not has_file and not text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Add an answer, a photo, a PDF or a voice note")
    sub = db.scalar(select(HomeworkSubmission).where(HomeworkSubmission.homework_id == hid, HomeworkSubmission.student_id == me.id))
    if sub and sub.status == "reviewed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already reviewed; cannot resubmit")
    saved = files.save_upload(sid, "submissions", file, SUBMIT) if has_file else None
    if not sub:
        sub = HomeworkSubmission(school_id=sid, created_by=user.id, homework_id=hid, student_id=me.id)
        db.add(sub)
    if saved:
        files.remove(sub.file_path)
        sub.file_path, sub.content_type, sub.original_name = saved
    sub.text = text.strip()
    sub.status, sub.feedback, sub.grade, sub.reviewed_at = "submitted", "", "", None
    sub.submitted_at = datetime.now(timezone.utc)
    sub.is_late = date.today() > h.due_date
    db.commit()
    return sub


def _sub_access(db: Session, user: User, sid: int, subid: int) -> tuple[HomeworkSubmission, Homework]:
    sub = get_or_404(db, HomeworkSubmission, subid, sid)
    h = get_or_404(db, Homework, sub.homework_id, sid)
    if user.role == Role.student.value:
        me = student_of(db, user)
        if not me or me.id != sub.student_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your submission")
    elif user.role == Role.parent.value:
        if sub.student_id not in child_ids(db, user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your child's submission")
    else:
        _owner_or_admin(db, user, h)
    return sub, h


@router.get("/submissions/{subid}/file")
def submission_file(subid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    sub, _ = _sub_access(db, user, sid, subid)
    return files.serve(sid, sub.file_path, sub.content_type, sub.original_name)


@router.patch("/submissions/{subid}/review", response_model=SubmissionOut)
def review(subid: int, body: ReviewIn, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    sub, h = _sub_access(db, user, sid, subid)
    sub.status, sub.feedback, sub.grade = body.status, body.feedback, body.grade
    sub.reviewed_at = datetime.now(timezone.utc)
    stu = get_or_404(db, Student, sub.student_id, sid)
    notify(db, sid, [student_user_id(db, stu.id), *parent_user_ids(db, stu.id)], "homework", f"notif.homework_{body.status}",
           {"name": stu.user.full_name, "title": h.title}, "homework")  # fmt: skip
    db.commit()
    return sub
