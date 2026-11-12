"""Phase 1+2 schema: tenancy, structure, people, OTP, attendance, timetable, homework, leave, notifications.
Every school-owned table uses TenantMixin."""
import enum
from datetime import date, datetime, time, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    teacher = "teacher"
    student = "student"
    parent = "parent"


class TenantMixin:
    """school_id + audit columns on every school-owned table."""

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --------------------------------------------------------------------------- tenancy
class School(Base):
    __tablename__ = "schools"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    address: Mapped[str] = mapped_column(Text, default="")
    district: Mapped[str] = mapped_column(String(100), default="")
    mandal: Mapped[str] = mapped_column(String(100), default="")
    logo_url: Mapped[str] = mapped_column(String(500), default="")
    default_language: Mapped[str] = mapped_column(String(5), default="en")
    headmaster_name: Mapped[str] = mapped_column(String(120), default="")
    headmaster_phone: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AcademicYear(TenantMixin, Base):
    __tablename__ = "academic_years"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(20))  # "2026-27"
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- structure
class SchoolClass(TenantMixin, Base):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("school_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))  # "10"
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    sections: Mapped[list["Section"]] = relationship(back_populates="school_class", cascade="all, delete-orphan")


class Section(TenantMixin, Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("school_id", "class_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    name: Mapped[str] = mapped_column(String(10))  # "A"
    class_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True, index=True)
    school_class: Mapped[SchoolClass] = relationship(back_populates="sections")


class Subject(TenantMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("school_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(20), default="")


class TeacherAssignment(TenantMixin, Base):
    """Teacher teaches <subject> in <section>."""

    __tablename__ = "teacher_assignments"
    __table_args__ = (UniqueConstraint("teacher_id", "section_id", "subject_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)


# --------------------------------------------------------------------------- people
class User(TenantMixin, Base):
    """Login identity. school_id is the owning school (superadmin rows use the platform school, id=1 is NOT assumed:
    superadmin has school_id NULL -> so this column is nullable via override below)."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("school_id", "role", "login_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True, nullable=True)  # type: ignore[assignment]
    role: Mapped[str] = mapped_column(String(12), index=True)
    login_id: Mapped[str] = mapped_column(String(64))  # username / employee id / admission no / mobile
    password_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)  # parents: OTP only
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    language: Mapped[str] = mapped_column(String(5), default="en")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Teacher(TenantMixin, Base):
    __tablename__ = "teachers"
    __table_args__ = (UniqueConstraint("school_id", "employee_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    employee_id: Mapped[str] = mapped_column(String(32))
    qualification: Mapped[str] = mapped_column(String(200), default="")
    joining_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    photo_url: Mapped[str] = mapped_column(String(500), default="")
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class Student(TenantMixin, Base):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("school_id", "admission_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    admission_no: Mapped[str] = mapped_column(String(32))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    roll_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dob: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(10), default="")
    photo_url: Mapped[str] = mapped_column(String(500), default="")
    parent_mobile: Mapped[str] = mapped_column(String(20), index=True)
    address: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), default="")
    medical_notes: Mapped[str] = mapped_column(Text, default="")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # soft delete
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class Parent(TenantMixin, Base):
    __tablename__ = "parents"
    __table_args__ = (UniqueConstraint("school_id", "mobile"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    mobile: Mapped[str] = mapped_column(String(20))
    relation: Mapped[str] = mapped_column(String(30), default="")
    alert_channels: Mapped[list] = mapped_column(JSON, default=lambda: ["app"])
    emergency_contact: Mapped[str] = mapped_column(String(20), default="")
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class StudentParent(TenantMixin, Base):
    __tablename__ = "student_parents"
    __table_args__ = (UniqueConstraint("student_id", "parent_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id"), index=True)


class OtpCode(TenantMixin, Base):
    __tablename__ = "otp_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    mobile: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


# =========================================================================== Phase 2
class Notification(TenantMixin, Base):
    """In-app notification (attendance alerts, leave steps). Push/SMS channels come later."""

    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # attendance | leave | homework
    key: Mapped[str] = mapped_column(String(80))  # i18n key, e.g. "notif.attendance_absent"; UI translates it
    params: Mapped[dict] = mapped_column(JSON, default=dict)  # interpolation values (child name, date ...)
    link: Mapped[str] = mapped_column(String(200), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)


# ---- attendance
class AttendanceSession(TenantMixin, Base):
    """One marking event: <section, date, period>. period 0 = whole-day register."""

    __tablename__ = "attendance_sessions"
    __table_args__ = (UniqueConstraint("school_id", "section_id", "date", "period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    period: Mapped[int] = mapped_column(Integer, default=0)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    marked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual | face
    records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class AttendanceRecord(TenantMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("session_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("attendance_sessions.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String(10))  # present | absent | late
    note: Mapped[str] = mapped_column(String(200), default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # face mode only
    session: Mapped[AttendanceSession] = relationship(back_populates="records")


# ---- timetable
class Period(TenantMixin, Base):
    __tablename__ = "periods"
    __table_args__ = (UniqueConstraint("school_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(Integer)  # 1..n
    label: Mapped[str] = mapped_column(String(40), default="")
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_break: Mapped[bool] = mapped_column(Boolean, default=False)


class TimetableEntry(TenantMixin, Base):
    __tablename__ = "timetable_entries"
    __table_args__ = (UniqueConstraint("school_id", "section_id", "day", "period_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    day: Mapped[int] = mapped_column(Integer)  # 0=Mon .. 5=Sat
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True, index=True)
    room: Mapped[str] = mapped_column(String(30), default="")


class TimetableUpload(TenantMixin, Base):
    """Teacher-uploaded timetable for a section: an image (stored on disk) or plain text."""

    __tablename__ = "timetable_uploads"
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # image | text
    text: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(300), default="")
    content_type: Mapped[str] = mapped_column(String(60), default="")
    original_name: Mapped[str] = mapped_column(String(200), default="")
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


# ---- homework
class Homework(TenantMixin, Base):
    __tablename__ = "homework"
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date] = mapped_column(Date)
    file_path: Mapped[str] = mapped_column(String(300), default="")
    content_type: Mapped[str] = mapped_column(String(80), default="")
    original_name: Mapped[str] = mapped_column(String(200), default="")


class HomeworkSubmission(TenantMixin, Base):
    __tablename__ = "homework_submissions"
    __table_args__ = (UniqueConstraint("homework_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    homework_id: Mapped[int] = mapped_column(ForeignKey("homework.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(300), default="")  # photo, PDF or voice note
    content_type: Mapped[str] = mapped_column(String(80), default="")
    original_name: Mapped[str] = mapped_column(String(200), default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12), default="submitted")  # submitted | reviewed | returned
    feedback: Mapped[str] = mapped_column(Text, default="")
    grade: Mapped[str] = mapped_column(String(20), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---- leave
class LeaveRequest(TenantMixin, Base):
    """Student chain: pending_parent -> pending_teacher -> approved (admin view-only).
    Teacher chain: pending_admin -> approved. Any step can reject; applicant can cancel while pending."""

    __tablename__ = "leave_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    applicant_role: Mapped[str] = mapped_column(String(12))  # student | teacher
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True, index=True)
    leave_type: Mapped[str] = mapped_column(String(20))
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(300), default="")
    content_type: Mapped[str] = mapped_column(String(80), default="")
    original_name: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), index=True)
    approvals: Mapped[list["LeaveApproval"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="LeaveApproval.id"
    )


class LeaveApproval(TenantMixin, Base):
    __tablename__ = "leave_approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests.id"), index=True)
    step: Mapped[str] = mapped_column(String(12))  # parent | teacher | admin
    approver_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(10))  # approved | rejected
    comment: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    request: Mapped[LeaveRequest] = relationship(back_populates="approvals")


# =========================================================================== Phase 3: assessment
class Quiz(TenantMixin, Base):
    """Teacher-built quiz for a section+subject. draft -> published -> closed. source=pdf means AI-drafted from a PDF
    (stub LLM for now); it still starts as draft and only goes live when the teacher publishes it."""

    __tablename__ = "quizzes"
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual | pdf
    source_file: Mapped[str] = mapped_column(String(300), default="")  # kept for audit, never served
    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="QuizQuestion.position"
    )


class QuizQuestion(TenantMixin, Base):
    """qtype: mcq | true_false | fill_blank | descriptive.
    answer: mcq -> option index (int); true_false -> bool; fill_blank -> list of accepted strings; descriptive -> model answer."""

    __tablename__ = "quiz_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    qtype: Mapped[str] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[object] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(String(100), default="")
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")  # easy | medium | hard
    marks: Mapped[float] = mapped_column(Float, default=1.0)
    quiz: Mapped[Quiz] = relationship(back_populates="questions")


class QuizAttempt(TenantMixin, Base):
    """One attempt per student per quiz. status: in_progress -> submitted (descriptive answers await a teacher) -> graded."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (UniqueConstraint("quiz_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="in_progress")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    answers: Mapped[list["AttemptAnswer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class AttemptAnswer(TenantMixin, Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"), index=True)
    answer: Mapped[object] = mapped_column(JSON, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None = awaiting teacher (descriptive)
    marks_awarded: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")
    attempt: Mapped[QuizAttempt] = relationship(back_populates="answers")


class Exam(TenantMixin, Base):
    """kind: mock (practice, shown on the progress graph but not in the report-card grade) | main (graded).
    Marks are entered by the assigned teacher; results become visible to students/parents once published."""

    __tablename__ = "exams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(6), index=True)  # mock | main
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    exam_date: Mapped[date] = mapped_column(Date)
    max_marks: Mapped[float] = mapped_column(Float)
    pass_marks: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft | published (results visible)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExamPaper(TenantMixin, Base):
    """Question paper (visible to the section) or answer key (staff only). One file per kind per exam."""

    __tablename__ = "exam_papers"
    __table_args__ = (UniqueConstraint("exam_id", "kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    kind: Mapped[str] = mapped_column(String(6))  # paper | key
    file_path: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(80))
    original_name: Mapped[str] = mapped_column(String(200))


class Mark(TenantMixin, Base):
    __tablename__ = "marks"
    __table_args__ = (UniqueConstraint("exam_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    absent: Mapped[bool] = mapped_column(Boolean, default=False)
    remarks: Mapped[str] = mapped_column(String(200), default="")
