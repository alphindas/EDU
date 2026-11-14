"""Teachers, students, parents. Role rules:
  admin   : full CRUD in own school
  teacher : read students of sections they teach / are class teacher of; read teacher directory
  student : read self only
  parent  : read own children only
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import child_ids, current_user, parent_of, require_roles, student_of, teacher_of, tenant_id
from ..models import (
    Parent,
    Role,
    SchoolClass,
    Section,
    Student,
    StudentParent,
    Teacher,
    TeacherAssignment,
    User,
)
from ..schemas import Page, ParentOut, StudentIn, StudentOut, StudentPatch, TeacherIn, TeacherOut, TeacherPatch
from ..security import hash_password
from .structure import get_or_404

router = APIRouter(tags=["people"])
admin_only = require_roles(Role.admin)
staff = require_roles(Role.admin, Role.teacher)


# ---------------------------------------------------------------- serializers
def teacher_out(t: Teacher, temp: str | None = None) -> TeacherOut:
    u = t.user
    return TeacherOut(
        id=t.id, user_id=t.user_id, employee_id=t.employee_id, full_name=u.full_name, phone=u.phone, email=u.email,
        qualification=t.qualification, joining_date=t.joining_date, photo_url=t.photo_url,
        is_active=u.is_active, temp_password=temp,
    )  # fmt: skip


def student_out(s: Student, temp: str | None = None) -> StudentOut:
    return StudentOut(
        id=s.id, admission_no=s.admission_no, full_name=s.user.full_name, class_id=s.class_id,
        section_id=s.section_id, roll_no=s.roll_no, dob=s.dob, gender=s.gender, photo_url=s.photo_url,
        parent_mobile=s.parent_mobile, address=s.address, language=s.user.language, category=s.category,
        medical_notes=s.medical_notes, temp_password=temp,
    )  # fmt: skip


def dob_password(dob) -> str:
    """First-login password: DOB as DDMMYYYY (forced change on first login)."""
    return dob.strftime("%d%m%Y")


def teacher_section_ids(db: Session, user: User) -> set[int]:
    t = teacher_of(db, user)
    if not t:
        return set()
    ids = set(db.scalars(select(Section.id).where(Section.class_teacher_id == t.id)))
    ids |= set(db.scalars(select(TeacherAssignment.section_id).where(TeacherAssignment.teacher_id == t.id)))
    return ids


# ---------------------------------------------------------------- teachers
@router.get("/teachers", response_model=Page[TeacherOut])
def list_teachers(
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(staff),
    sid: int = Depends(tenant_id),
    db: Session = Depends(get_db),
):
    base = select(Teacher).join(User, User.id == Teacher.user_id).where(Teacher.school_id == sid)
    if q:
        like = f"%{q}%"
        base = base.where(or_(User.full_name.ilike(like), Teacher.employee_id.ilike(like)))
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(Teacher.employee_id).limit(limit).offset(offset)).all()
    return Page(items=[teacher_out(t) for t in rows], total=total, limit=limit, offset=offset)


@router.post("/teachers", response_model=TeacherOut, status_code=201)
def create_teacher(
    body: TeacherIn, admin: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    temp = body.password or secrets.token_urlsafe(8)
    user = User(
        school_id=sid, created_by=admin.id, role=Role.teacher.value, login_id=body.employee_id,
        full_name=body.full_name, phone=body.phone, email=body.email,
        password_hash=hash_password(temp), must_change_password=True,
    )  # fmt: skip
    db.add(user)
    try:
        db.flush()
        t = Teacher(
            school_id=sid, created_by=admin.id, user_id=user.id, employee_id=body.employee_id,
            qualification=body.qualification, joining_date=body.joining_date, photo_url=body.photo_url,
        )  # fmt: skip
        db.add(t)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Employee ID already exists")
    return teacher_out(t, temp)


@router.get("/teachers/{tid}", response_model=TeacherOut)
def get_teacher(tid: int, _: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return teacher_out(get_or_404(db, Teacher, tid, sid))


@router.patch("/teachers/{tid}", response_model=TeacherOut)
def patch_teacher(
    tid: int, body: TeacherPatch, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    t = get_or_404(db, Teacher, tid, sid)
    for k, v in body.model_dump(exclude_unset=True).items():
        if k in ("full_name", "phone", "email", "is_active"):
            setattr(t.user, k, v)
        else:
            setattr(t, k, v)
    if body.is_active is False:  # deactivated teacher can no longer be a class teacher
        for sec in db.scalars(select(Section).where(Section.class_teacher_id == t.id)):
            sec.class_teacher_id = None
    db.commit()
    return teacher_out(t)


@router.delete("/teachers/{tid}", status_code=204)
def delete_teacher(tid: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Soft delete: login is disabled, records stay (audit)."""
    t = get_or_404(db, Teacher, tid, sid)
    t.user.is_active = False
    for sec in db.scalars(select(Section).where(Section.class_teacher_id == t.id)):
        sec.class_teacher_id = None
    for a in db.scalars(select(TeacherAssignment).where(TeacherAssignment.teacher_id == t.id)):
        db.delete(a)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- parents (auto-created)
def get_or_create_parent(db: Session, sid: int, mobile: str, name: str, relation: str, creator: int) -> Parent:
    parent = db.scalar(select(Parent).where(Parent.school_id == sid, Parent.mobile == mobile))
    if parent:
        return parent
    user = User(
        school_id=sid, created_by=creator, role=Role.parent.value, login_id=mobile,
        full_name=name or f"Parent {mobile[-4:]}", phone=mobile, password_hash=None,
    )  # fmt: skip
    db.add(user)
    db.flush()
    parent = Parent(school_id=sid, created_by=creator, user_id=user.id, mobile=mobile, relation=relation)
    db.add(parent)
    db.flush()
    return parent


def link(db: Session, sid: int, student_id: int, parent_id: int) -> None:
    exists = db.scalar(
        select(StudentParent.id).where(StudentParent.student_id == student_id, StudentParent.parent_id == parent_id)
    )
    if not exists:
        db.add(StudentParent(school_id=sid, student_id=student_id, parent_id=parent_id))


def _validate_placement(db: Session, sid: int, class_id: int, section_id: int) -> None:
    get_or_404(db, SchoolClass, class_id, sid)
    sec = get_or_404(db, Section, section_id, sid)
    if sec.class_id != class_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Section does not belong to that class")


# ---------------------------------------------------------------- students
@router.get("/students", response_model=Page[StudentOut])
def list_students(
    class_id: int | None = None,
    section_id: int | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_roles(Role.admin, Role.teacher, Role.parent)),
    sid: int = Depends(tenant_id),
    db: Session = Depends(get_db),
):
    base = select(Student).join(User, User.id == Student.user_id).where(
        Student.school_id == sid, Student.deleted_at.is_(None)
    )
    if user.role == Role.teacher.value:
        base = base.where(Student.section_id.in_(teacher_section_ids(db, user)))
    elif user.role == Role.parent.value:
        base = base.where(Student.id.in_(child_ids(db, user)))
    if class_id:
        base = base.where(Student.class_id == class_id)
    if section_id:
        base = base.where(Student.section_id == section_id)
    if q:
        like = f"%{q}%"
        base = base.where(or_(User.full_name.ilike(like), Student.admission_no.ilike(like)))
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(Student.section_id, Student.roll_no, Student.admission_no).limit(limit).offset(offset)).all()
    return Page(items=[student_out(s) for s in rows], total=total, limit=limit, offset=offset)


@router.post("/students", response_model=StudentOut, status_code=201)
def create_student(
    body: StudentIn, admin: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    _validate_placement(db, sid, body.class_id, body.section_id)
    temp = dob_password(body.dob)
    user = User(
        school_id=sid, created_by=admin.id, role=Role.student.value, login_id=body.admission_no,
        full_name=body.full_name, language=body.language, password_hash=hash_password(temp), must_change_password=True,
    )  # fmt: skip
    db.add(user)
    try:
        db.flush()
        s = Student(
            school_id=sid, created_by=admin.id, user_id=user.id, admission_no=body.admission_no,
            class_id=body.class_id, section_id=body.section_id, roll_no=body.roll_no, dob=body.dob,
            gender=body.gender, photo_url=body.photo_url, parent_mobile=body.parent_mobile, address=body.address,
            category=body.category, medical_notes=body.medical_notes,
        )  # fmt: skip
        db.add(s)
        db.flush()
        parent = get_or_create_parent(db, sid, body.parent_mobile, body.parent_name, body.parent_relation, admin.id)
        link(db, sid, s.id, parent.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Admission number already exists")
    return student_out(s, temp)


def _authorise_student(db: Session, user: User, s: Student) -> None:
    if user.role == Role.admin.value:
        return
    if user.role == Role.teacher.value and s.section_id in teacher_section_ids(db, user):
        return
    if user.role == Role.student.value and (me := student_of(db, user)) and me.id == s.id:
        return
    if user.role == Role.parent.value and s.id in child_ids(db, user):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this student")


@router.get("/students/{stid}", response_model=StudentOut)
def get_student(stid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    s = get_or_404(db, Student, stid, sid)
    if s.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    _authorise_student(db, user, s)
    return student_out(s)


@router.patch("/students/{stid}", response_model=StudentOut)
def patch_student(
    stid: int, body: StudentPatch, admin: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    s = get_or_404(db, Student, stid, sid)
    data = body.model_dump(exclude_unset=True)
    cls, sec = data.get("class_id", s.class_id), data.get("section_id", s.section_id)
    if "class_id" in data or "section_id" in data:
        _validate_placement(db, sid, cls, sec)
    for k in ("full_name", "language"):
        if k in data:
            setattr(s.user, k, data.pop(k))
    parent_name = data.pop("parent_name", "")
    new_mobile = data.get("parent_mobile")
    for k, v in data.items():
        setattr(s, k, v)
    if new_mobile:
        parent = get_or_create_parent(db, sid, new_mobile, parent_name, "", admin.id)
        link(db, sid, s.id, parent.id)
        for old in db.scalars(select(StudentParent).where(StudentParent.student_id == s.id, StudentParent.parent_id != parent.id)):
            db.delete(old)  # mobile change = new guardian replaces old link
    db.commit()
    return student_out(s)


@router.delete("/students/{stid}", status_code=204)
def delete_student(stid: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Soft delete + login disabled."""
    s = get_or_404(db, Student, stid, sid)
    s.deleted_at = datetime.now(timezone.utc)
    s.user.is_active = False
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- parents
def parent_out(db: Session, p: Parent) -> ParentOut:
    kids = db.scalars(
        select(Student).join(StudentParent, StudentParent.student_id == Student.id).where(
            StudentParent.parent_id == p.id, Student.deleted_at.is_(None)
        )
    ).all()
    return ParentOut(
        id=p.id, full_name=p.user.full_name, mobile=p.mobile, relation=p.relation, language=p.user.language,
        alert_channels=p.alert_channels, emergency_contact=p.emergency_contact, children=[student_out(k) for k in kids],
    )  # fmt: skip


@router.get("/parents", response_model=Page[ParentOut])
def list_parents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(admin_only),
    sid: int = Depends(tenant_id),
    db: Session = Depends(get_db),
):
    base = select(Parent).where(Parent.school_id == sid)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(Parent.id).limit(limit).offset(offset)).all()
    return Page(items=[parent_out(db, p) for p in rows], total=total, limit=limit, offset=offset)


@router.get("/parents/{pid}", response_model=ParentOut)
def get_parent(pid: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return parent_out(db, get_or_404(db, Parent, pid, sid))


@router.get("/me/children", response_model=list[StudentOut])
def my_children(user: User = Depends(require_roles(Role.parent)), db: Session = Depends(get_db)):
    p = parent_of(db, user)
    return parent_out(db, p).children if p else []
