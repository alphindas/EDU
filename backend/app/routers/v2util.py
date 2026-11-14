"""Shared helpers for EduNest 2.0 routers: who-can-see-whom, consent, burst rate limits, AI audit logging."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..deps import child_ids, student_of, teacher_of
from ..models import Role, SchoolClass, Section, Student, StudentParent, Parent, Teacher, TeacherAssignment, User
from ..models_v2 import AuditLog, StaffFlag, StudentPrefs

_hits: dict[int, deque] = defaultdict(deque)


def burst_limit(user_id: int) -> None:
    """Per-user sliding window on AI endpoints (EDUNEST_AI_PER_MINUTE)."""
    lim = get_settings().ai_per_minute
    now = time.monotonic()
    q = _hits[user_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= lim:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "CHITTI needs a short breather. Try again in a minute.")
    q.append(now)


def reset_burst() -> None:
    _hits.clear()


def me_student(db: Session, user: User) -> Student:
    s = student_of(db, user)
    if not s:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No student profile")
    return s


def class_name_of(db: Session, class_id: int | None) -> str | None:
    return db.scalar(select(SchoolClass.name).where(SchoolClass.id == class_id)) if class_id else None


def teacher_sections(db: Session, user: User) -> set[int]:
    t = teacher_of(db, user)
    if not t:
        return set()
    ids = set(db.scalars(select(Section.id).where(Section.class_teacher_id == t.id)))
    ids |= set(db.scalars(select(TeacherAssignment.section_id).where(TeacherAssignment.teacher_id == t.id)))
    return ids


def can_view_student(db: Session, user: User, stu: Student) -> bool:
    if user.role == Role.admin.value:
        return True
    if user.role == Role.student.value:
        return stu.user_id == user.id
    if user.role == Role.parent.value:
        return stu.id in child_ids(db, user)
    if user.role == Role.teacher.value:
        return stu.section_id in teacher_sections(db, user)
    return False


def target_student(db: Session, user: User, sid: int, student_id: int | None) -> Student:
    """Self for students; otherwise the requested student after a row-level check (404 hides existence)."""
    if user.role == Role.student.value and student_id is None:
        return me_student(db, user)
    if student_id is None:
        if user.role == Role.parent.value:
            kids = sorted(child_ids(db, user))
            if kids:
                student_id = kids[0]
        if student_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
    stu = db.scalar(select(Student).where(Student.id == student_id, Student.school_id == sid))
    if not stu or not can_view_student(db, user, stu):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    return stu


def consent_ok(db: Session, stu: Student) -> bool:
    if not get_settings().require_ai_consent:
        return True
    p = db.scalar(select(StudentPrefs).where(StudentPrefs.student_id == stu.id))
    return bool(p and p.ai_consent)


def require_consent(db: Session, user: User) -> Student | None:
    if user.role != Role.student.value:
        return None
    stu = me_student(db, user)
    if not consent_ok(db, stu):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "parent_consent_required")
    return stu


def is_counsellor(db: Session, user: User) -> bool:
    return bool(db.scalar(select(StaffFlag.counsellor).where(StaffFlag.user_id == user.id)))


def log_ai(db: Session, sid: int, user: User, path: str, detail: str) -> None:
    db.add(AuditLog(school_id=sid, user_id=user.id, role=user.role, action="AI", path=path, status_code=200, detail=detail[:400]))


def section_teacher_user_ids(db: Session, section_id: int) -> set[int]:
    ids = set(db.scalars(select(Teacher.user_id).join(TeacherAssignment, TeacherAssignment.teacher_id == Teacher.id)
                         .where(TeacherAssignment.section_id == section_id)))  # fmt: skip
    ct = db.scalar(select(Teacher.user_id).join(Section, Section.class_teacher_id == Teacher.id).where(Section.id == section_id))
    if ct:
        ids.add(ct)
    return ids


def parents_of_sections(db: Session, sections: set[int]) -> set[int]:
    return set(db.scalars(select(Parent.user_id).join(StudentParent, StudentParent.parent_id == Parent.id)
                          .join(Student, Student.id == StudentParent.student_id).where(Student.section_id.in_(sections or {-1}))))  # fmt: skip
