"""Phase 2 request/response models."""
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["present", "absent", "late"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- notifications
class NotificationOut(ORM):
    id: int
    kind: str
    key: str
    params: dict
    link: str
    read: bool
    created_at: datetime


# ---- attendance
class RecordIn(BaseModel):
    student_id: int
    status: Status
    note: str = Field(default="", max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1)


class MarkIn(BaseModel):
    section_id: int
    date: date
    period: int = Field(default=0, ge=0, le=12)  # 0 = whole-day register
    subject_id: int | None = None
    source: Literal["manual", "face"] = "manual"
    records: list[RecordIn] = Field(min_length=1, max_length=300)


class RecordOut(ORM):
    student_id: int
    status: str
    note: str
    confidence: float | None


class SessionOut(ORM):
    id: int
    section_id: int
    date: date
    period: int
    subject_id: int | None
    source: str
    marked_by: int | None
    records: list[RecordOut]


class SheetRow(BaseModel):
    student_id: int
    admission_no: str
    full_name: str
    roll_no: int | None
    status: str | None
    note: str


class SheetOut(BaseModel):
    section_id: int
    date: date
    period: int
    exists: bool
    source: str | None
    rows: list[SheetRow]


class SummaryRow(BaseModel):
    section_id: int
    total: int
    marked: bool
    present: int
    absent: int
    late: int


class HistoryItem(BaseModel):
    date: date
    period: int
    status: str
    note: str


class HistoryOut(BaseModel):
    student_id: int
    items: list[HistoryItem]
    present: int
    absent: int
    late: int
    percentage: float | None


class FaceStartIn(BaseModel):
    section_id: int
    period: int = Field(default=1, ge=0, le=12)


class FaceRowOut(BaseModel):
    student_id: int
    admission_no: str
    full_name: str
    status: Status
    confidence: float | None = None
    time: str | None = None


class FaceStatusOut(BaseModel):
    running: bool
    demo: bool
    period: int
    section_id: int
    total: int
    detected: list[FaceRowOut]  # students of this section recognised so far
    unmatched: int  # rows from the camera that are not in this section (dropped)


class FaceStopOut(BaseModel):
    """Proposal only. Nothing is saved until the teacher confirms via PUT /attendance/sessions (source=face)."""

    section_id: int
    period: int
    proposal: list[RecordIn]
    unmatched: int


# ---- timetable
class PeriodIn(BaseModel):
    number: int = Field(ge=1, le=15)
    label: str = Field(default="", max_length=40)
    start_time: time
    end_time: time
    is_break: bool = False

    @model_validator(mode="after")
    def _order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class PeriodPatch(BaseModel):
    number: int | None = Field(default=None, ge=1, le=15)
    label: str | None = Field(default=None, max_length=40)
    start_time: time | None = None
    end_time: time | None = None
    is_break: bool | None = None


class PeriodOut(ORM, PeriodIn):
    id: int


class EntryIn(BaseModel):
    section_id: int
    day: int = Field(ge=0, le=5)
    period_id: int
    subject_id: int
    teacher_id: int | None = None
    room: str = Field(default="", max_length=30)


class EntryOut(ORM, EntryIn):
    id: int


class UploadOut(ORM):
    id: int
    section_id: int
    kind: str
    text: str
    content_type: str
    original_name: str
    uploaded_by: int | None
    created_at: datetime


class TimetableOut(BaseModel):
    section_id: int
    entries: list[EntryOut]
    uploads: list[UploadOut]


# ---- homework
class SubmissionOut(ORM):
    id: int
    homework_id: int
    student_id: int
    text: str
    original_name: str
    content_type: str
    submitted_at: datetime
    is_late: bool
    status: str
    feedback: str
    grade: str
    reviewed_at: datetime | None


class HomeworkOut(BaseModel):
    id: int
    section_id: int
    subject_id: int
    teacher_id: int
    title: str
    description: str
    due_date: date
    attachment_name: str
    created_at: datetime
    total_students: int | None = None
    submitted_count: int | None = None
    reviewed_count: int | None = None
    my_submission: SubmissionOut | None = None


class SubmissionRow(BaseModel):
    student_id: int
    admission_no: str
    full_name: str
    roll_no: int | None
    submission: SubmissionOut | None


class ReviewIn(BaseModel):
    status: Literal["reviewed", "returned"] = "reviewed"
    feedback: str = Field(default="", max_length=2000)
    grade: str = Field(default="", max_length=20)


# ---- leave
LEAVE_TYPES = ("sick", "casual", "family", "other")


class ApprovalOut(BaseModel):
    step: str
    approver_name: str
    decision: str
    comment: str
    decided_at: datetime


class LeaveOut(BaseModel):
    id: int
    applicant_role: str
    applicant_name: str
    student_id: int | None
    teacher_id: int | None
    section_id: int | None
    leave_type: str
    from_date: date
    to_date: date
    days: int
    reason: str
    attachment_name: str
    status: str
    created_at: datetime
    approvals: list[ApprovalOut]
    can_act: bool  # caller may approve/reject right now
    can_cancel: bool


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str = Field(default="", max_length=1000)


# ---- ID card
class IdVerifyIn(BaseModel):
    payload: str = Field(max_length=300)


class IdCardOut(BaseModel):
    student_id: int
    admission_no: str
    full_name: str
    class_name: str
    section_name: str
    roll_no: int | None
    dob: date
    gender: str
    photo_url: str
    parent_mobile: str
    school_name: str
    school_code: str
    school_address: str
    logo_url: str
    academic_year: str
    qr_payload: str


class IdVerifyOut(BaseModel):
    valid: bool
    reason: str = ""
    student: IdCardOut | None = None
