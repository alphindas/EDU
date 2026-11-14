"""In-app notifications. Text is an i18n key + params; the UI translates in the reader's language."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Notification, Parent, Role, Section, Student, StudentParent, Teacher, User


def notify(db: Session, school_id: int, user_ids, kind: str, key: str, params: dict | None = None, link: str = "") -> None:
    for uid in {u for u in user_ids if u}:
        db.add(Notification(school_id=school_id, user_id=uid, kind=kind, key=key, params=params or {}, link=link))


def parent_user_ids(db: Session, student_id: int) -> list[int]:
    return list(
        db.scalars(
            select(Parent.user_id).join(StudentParent, StudentParent.parent_id == Parent.id).where(StudentParent.student_id == student_id)
        )
    )


def class_teacher_user_id(db: Session, section_id: int) -> int | None:
    return db.scalar(
        select(Teacher.user_id).join(Section, Section.class_teacher_id == Teacher.id).where(Section.id == section_id)
    )


def admin_user_ids(db: Session, school_id: int) -> list[int]:
    return list(db.scalars(select(User.id).where(User.school_id == school_id, User.role == Role.admin.value, User.is_active.is_(True))))


def student_user_id(db: Session, student_id: int) -> int | None:
    return db.scalar(select(Student.user_id).where(Student.id == student_id))
