"""Leave workflow.
  Student: apply -> parent approves -> class teacher approves -> APPROVED (admin sees it, view-only)
  Teacher: apply -> admin approves -> APPROVED
Any step can reject. The applicant can cancel while pending. Every transition is recorded in leave_approvals and
notifies the next actor (or the applicant)."""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import files
from ..db import get_db
from ..deps import child_ids, current_user, student_of, teacher_of, tenant_id
from ..models import LeaveApproval, LeaveRequest, Role, Section, Student, User
from ..notify import admin_user_ids, class_teacher_user_id, notify, parent_user_ids
from ..schemas_p2 import LEAVE_TYPES, ApprovalOut, DecisionIn, LeaveOut
from .structure import get_or_404

router = APIRouter(prefix="/leave", tags=["leave"])
ATTACH = {**files.IMAGE, **files.DOC}
MAX_DAYS = 60
PENDING = ("pending_parent", "pending_teacher", "pending_admin")


# ------------------------------------------------------------------ visibility / permissions
def _ctx(db: Session, user: User) -> dict:
    c: dict = {"kids": set(), "teacher": None, "sections": set(), "student": None}
    if user.role == Role.parent.value:
        c["kids"] = child_ids(db, user)
    elif user.role == Role.teacher.value:
        c["teacher"] = teacher_of(db, user)
        if c["teacher"]:
            c["sections"] = set(db.scalars(select(Section.id).where(Section.class_teacher_id == c["teacher"].id)))
    elif user.role == Role.student.value:
        c["student"] = student_of(db, user)
    return c


def _section_of(db: Session, r: LeaveRequest) -> int | None:
    if r.student_id is None:
        return None
    return db.scalar(select(Student.section_id).where(Student.id == r.student_id))


def _visible(db: Session, user: User, r: LeaveRequest, c: dict) -> bool:
    if r.applicant_user_id == user.id:
        return True
    if user.role == Role.admin.value:
        return r.applicant_role == "teacher" or r.status == "approved"  # student leave: only once fully approved
    if user.role == Role.parent.value:
        return r.student_id in c["kids"]
    if user.role == Role.teacher.value and r.applicant_role == "student" and _section_of(db, r) in c["sections"]:
        if r.status in ("pending_teacher", "approved"):
            return True
        return r.status == "rejected" and any(a.step == "teacher" for a in r.approvals)
    return False


def _can_act(db: Session, user: User, r: LeaveRequest, c: dict) -> bool:
    if r.status == "pending_parent":
        return user.role == Role.parent.value and r.student_id in c["kids"]
    if r.status == "pending_teacher":
        return user.role == Role.teacher.value and _section_of(db, r) in c["sections"]
    if r.status == "pending_admin":
        return user.role == Role.admin.value
    return False


def _name(db: Session, r: LeaveRequest) -> str:
    return db.scalar(select(User.full_name).where(User.id == r.applicant_user_id)) or ""


def _out(db: Session, user: User, r: LeaveRequest, c: dict) -> LeaveOut:
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_([a.approver_user_id for a in r.approvals] or [-1])))}
    return LeaveOut(
        id=r.id, applicant_role=r.applicant_role, applicant_name=_name(db, r), student_id=r.student_id, teacher_id=r.teacher_id,
        section_id=_section_of(db, r), leave_type=r.leave_type, from_date=r.from_date, to_date=r.to_date,
        days=(r.to_date - r.from_date).days + 1, reason=r.reason, attachment_name=r.original_name, status=r.status,
        created_at=r.created_at,
        approvals=[ApprovalOut(step=a.step, approver_name=names.get(a.approver_user_id, ""), decision=a.decision,
                               comment=a.comment, decided_at=a.decided_at) for a in r.approvals],
        can_act=_can_act(db, user, r, c), can_cancel=r.applicant_user_id == user.id and r.status in PENDING,
    )  # fmt: skip


def _load(db: Session, user: User, sid: int, rid: int) -> tuple[LeaveRequest, dict]:
    r = get_or_404(db, LeaveRequest, rid, sid)
    c = _ctx(db, user)
    if not _visible(db, user, r, c):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LeaveRequest not found")  # don't reveal existence
    return r, c


# ------------------------------------------------------------------ apply
@router.post("", response_model=LeaveOut, status_code=201)
def apply(
    leave_type: str = Form(...), from_date: date = Form(...), to_date: date = Form(...),
    reason: str = Form("", max_length=2000), file: UploadFile | None = File(None),
    user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    if user.role not in (Role.student.value, Role.teacher.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only students and teachers apply for leave")
    if leave_type not in LEAVE_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"leave_type must be one of {', '.join(LEAVE_TYPES)}")
    if to_date < from_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "to_date is before from_date")
    if (to_date - from_date).days + 1 > MAX_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Leave longer than {MAX_DAYS} days")
    overlap = db.scalar(select(LeaveRequest.id).where(
        LeaveRequest.school_id == sid, LeaveRequest.applicant_user_id == user.id,
        LeaveRequest.status.in_([*PENDING, "approved"]), LeaveRequest.from_date <= to_date, LeaveRequest.to_date >= from_date,
    ).limit(1))  # fmt: skip
    if overlap:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have leave overlapping these dates")

    r = LeaveRequest(school_id=sid, created_by=user.id, applicant_user_id=user.id, applicant_role=user.role,
                     leave_type=leave_type, from_date=from_date, to_date=to_date, reason=reason.strip(), status="")  # fmt: skip
    if user.role == Role.student.value:
        me = student_of(db, user)
        if not me:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No student profile")
        r.student_id, r.status = me.id, "pending_parent"
    else:
        me = teacher_of(db, user)
        if not me:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No teacher profile")
        r.teacher_id, r.status = me.id, "pending_admin"
    if file and file.filename:
        r.file_path, r.content_type, r.original_name = files.save_upload(sid, "leave", file, ATTACH)
    db.add(r)
    db.flush()
    params = {"name": user.full_name, "from": from_date.isoformat(), "to": to_date.isoformat()}
    if r.status == "pending_parent":
        notify(db, sid, parent_user_ids(db, r.student_id), "leave", "notif.leave_needs_parent", params, "leave")
    else:
        notify(db, sid, admin_user_ids(db, sid), "leave", "notif.leave_needs_admin", params, "leave")
    db.commit()
    return _out(db, user, r, _ctx(db, user))


# ------------------------------------------------------------------ list / read
@router.get("", response_model=list[LeaveOut])
def list_leave(
    status_: str | None = Query(None, alias="status"), limit: int = Query(100, ge=1, le=200),
    user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    q = select(LeaveRequest).where(LeaveRequest.school_id == sid)
    if status_:
        q = q.where(LeaveRequest.status == status_)
    if user.role == Role.student.value:
        q = q.where(LeaveRequest.applicant_user_id == user.id)
    elif user.role == Role.admin.value:
        q = q.where(or_(LeaveRequest.applicant_role == "teacher", LeaveRequest.status == "approved"))
    elif user.role == Role.parent.value:
        q = q.where(LeaveRequest.student_id.in_(child_ids(db, user) or {-1}))
    elif user.role == Role.teacher.value:  # own requests + students of the sections I am class teacher of
        mine = _ctx(db, user)["sections"]
        in_my_sections = select(Student.id).where(Student.section_id.in_(mine or {-1}))
        q = q.where(or_(LeaveRequest.applicant_user_id == user.id, LeaveRequest.student_id.in_(in_my_sections)))
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
    c = _ctx(db, user)
    rows = db.scalars(q.order_by(LeaveRequest.id.desc()).limit(limit)).all()
    return [_out(db, user, r, c) for r in rows if _visible(db, user, r, c)]  # python filter = same rules as detail view


@router.get("/{rid}", response_model=LeaveOut)
def get_leave(rid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r, c = _load(db, user, sid, rid)
    return _out(db, user, r, c)


@router.get("/{rid}/attachment")
def attachment(rid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r, _ = _load(db, user, sid, rid)
    return files.serve(sid, r.file_path, r.content_type, r.original_name)


# ------------------------------------------------------------------ decide / cancel
@router.post("/{rid}/decision", response_model=LeaveOut)
def decide(rid: int, body: DecisionIn, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r, c = _load(db, user, sid, rid)
    if r.applicant_role == "student" and user.role == Role.admin.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin can view student leave but not decide it")
    if r.status not in PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "This request is no longer pending")
    if not _can_act(db, user, r, c):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "It is not your turn to decide this request")

    step = {"pending_parent": "parent", "pending_teacher": "teacher", "pending_admin": "admin"}[r.status]
    approve = body.decision == "approve"
    db.add(LeaveApproval(school_id=sid, created_by=user.id, request_id=r.id, step=step, approver_user_id=user.id,
                         decision="approved" if approve else "rejected", comment=body.comment.strip()))  # fmt: skip
    params = {"name": _name(db, r), "from": r.from_date.isoformat(), "to": r.to_date.isoformat()}
    if not approve:
        r.status = "rejected"
        key = "notif.leave_rejected"
    elif step == "parent":
        r.status = "pending_teacher"
        key = ""
        ct = class_teacher_user_id(db, _section_of(db, r))
        notify(db, sid, [ct], "leave", "notif.leave_needs_teacher", params, "leave")
    else:
        r.status = "approved"
        key = "notif.leave_approved"
    if key:
        who = [r.applicant_user_id] + (parent_user_ids(db, r.student_id) if r.student_id else [])
        notify(db, sid, [w for w in who if w != user.id], "leave", key, params, "leave")
    elif step == "parent":
        notify(db, sid, [r.applicant_user_id], "leave", "notif.leave_parent_approved", params, "leave")
    db.commit()
    db.refresh(r)
    return _out(db, user, r, c)


@router.post("/{rid}/cancel", response_model=LeaveOut)
def cancel(rid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r, c = _load(db, user, sid, rid)
    if r.applicant_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the applicant can cancel")
    if r.status not in PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only pending requests can be cancelled")
    r.status = "cancelled"
    db.commit()
    return _out(db, user, r, c)
