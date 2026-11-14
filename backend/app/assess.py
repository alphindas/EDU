"""Shared Phase 3 helpers: grade scale, percentages, teacher<->section checks, aware datetimes."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Student, Teacher, TeacherAssignment

# (minimum percentage, grade). Edit here to change the school-wide scale.
GRADE_SCALE = [(90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (50, "C"), (35, "D"), (0, "E")]


def grade_for(pct: float | None) -> str | None:
    if pct is None:
        return None
    return next(g for lo, g in GRADE_SCALE if pct >= lo)


def pct(marks: float | None, max_marks: float) -> float | None:
    if marks is None or not max_marks:
        return None
    return round(marks * 100 / max_marks, 1)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite hands timezone-aware columns back naive (UTC); normalise before comparing with now()."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def assert_assigned(db: Session, sid: int, teacher: Teacher | None, section_id: int, subject_id: int) -> Teacher:
    """The teacher must be assigned this subject in this section (same rule as homework)."""
    if not teacher or not db.scalar(select(TeacherAssignment.id).where(
        TeacherAssignment.school_id == sid, TeacherAssignment.teacher_id == teacher.id,
        TeacherAssignment.section_id == section_id, TeacherAssignment.subject_id == subject_id,
    )):  # fmt: skip
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not teach this subject in this section")
    return teacher


def section_students(db: Session, sid: int, section_id: int) -> list[Student]:
    return list(db.scalars(
        select(Student).where(Student.school_id == sid, Student.section_id == section_id, Student.deleted_at.is_(None))
        .order_by(Student.roll_no, Student.admission_no)
    ))  # fmt: skip
