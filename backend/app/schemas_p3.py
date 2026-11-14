"""Phase 3 request/response models: quizzes, attempts, exams, marks, report card."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

QType = Literal["mcq", "true_false", "fill_blank", "descriptive"]
Difficulty = Literal["easy", "medium", "hard"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- quiz authoring
class QuestionIn(BaseModel):
    """Structure is checked on save; a *complete* answer key is only required to publish (AI drafts may lack one)."""

    qtype: QType
    text: str = Field(min_length=1, max_length=2000)
    options: list[str] = Field(default_factory=list, max_length=6)
    answer: int | bool | str | list[str] | None = None
    explanation: str = Field(default="", max_length=2000)
    topic: str = Field(default="", max_length=100)
    difficulty: Difficulty = "medium"
    marks: float = Field(default=1.0, gt=0, le=100)

    @model_validator(mode="after")
    def _shape(self):
        self.text = self.text.strip()
        if self.qtype == "mcq":
            self.options = [o.strip() for o in self.options]
            if len(self.options) < 2 or any(not o for o in self.options):
                raise ValueError("mcq needs at least 2 non-empty options")
            if self.answer is not None and (isinstance(self.answer, bool) or not isinstance(self.answer, int)
                                            or not 0 <= self.answer < len(self.options)):
                raise ValueError("mcq answer must be the index of an option")
        else:
            self.options = []
            if self.qtype == "true_false" and self.answer is not None and not isinstance(self.answer, bool):
                raise ValueError("true_false answer must be true or false")
            if self.qtype == "fill_blank":
                if isinstance(self.answer, str):
                    self.answer = [self.answer]
                if self.answer is not None and (not isinstance(self.answer, list) or any(not isinstance(a, str) for a in self.answer)):
                    raise ValueError("fill_blank answer must be a list of accepted strings")
                if self.answer is not None:
                    self.answer = [a.strip() for a in self.answer if a.strip()]
            if self.qtype == "descriptive" and self.answer is not None and not isinstance(self.answer, str):
                raise ValueError("descriptive answer must be text")
        return self

    def is_complete(self) -> bool:
        if self.qtype == "descriptive":
            return True  # model answer is optional; a teacher grades it by hand
        return self.answer is not None and self.answer != []


class QuizIn(BaseModel):
    section_id: int
    subject_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    time_limit_minutes: int | None = Field(default=None, ge=1, le=300)
    questions: list[QuestionIn] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title required")
        return v.strip()


class QuestionStaff(ORM):
    id: int
    position: int
    qtype: str
    text: str
    options: list[str]
    answer: int | bool | str | list[str] | None
    explanation: str
    topic: str
    difficulty: str
    marks: float


class QuestionPlay(ORM):
    """What a student sees while taking the quiz: no answer key, no explanation."""

    id: int
    qtype: str
    text: str
    options: list[str]
    marks: float


class AttemptBrief(ORM):
    id: int
    status: str
    score: float
    max_score: float
    submitted_at: datetime | None


class QuizOut(ORM):
    id: int
    section_id: int
    subject_id: int
    teacher_id: int
    title: str
    description: str
    status: str
    time_limit_minutes: int | None
    source: str
    created_at: datetime
    question_count: int = 0
    total_marks: float = 0
    attempt_count: int | None = None  # staff only
    pending_grading: int | None = None  # staff only: descriptive answers awaiting marks
    my_attempt: AttemptBrief | None = None  # student / parent-of-child view


class QuizDetail(QuizOut):
    questions: list[QuestionStaff] = []


# ---------------------------------------------------------------- attempts
class AttemptPlay(BaseModel):
    attempt_id: int
    quiz_id: int
    title: str
    started_at: datetime
    deadline: datetime | None
    questions: list[QuestionPlay]


class AnswerIn(BaseModel):
    question_id: int
    answer: int | bool | str | None = None


class SubmitIn(BaseModel):
    answers: list[AnswerIn] = Field(max_length=100)


class AnswerResult(BaseModel):
    answer_id: int
    question_id: int
    qtype: str
    text: str
    options: list[str]
    marks: float
    topic: str
    your_answer: int | bool | str | None
    correct_answer: int | bool | str | list[str] | None
    is_correct: bool | None
    marks_awarded: float | None
    explanation: str
    feedback: str


class AttemptResult(BaseModel):
    id: int
    quiz_id: int
    quiz_title: str
    student_id: int
    student_name: str
    status: str
    score: float
    max_score: float
    percentage: float | None
    submitted_at: datetime | None
    timed_out: bool
    answers: list[AnswerResult]


class AttemptRow(BaseModel):
    student_id: int
    admission_no: str
    full_name: str
    roll_no: int | None
    attempt: AttemptBrief | None
    attempt_id: int | None


class GradeIn(BaseModel):
    marks: float = Field(ge=0)
    feedback: str = Field(default="", max_length=2000)


# ---------------------------------------------------------------- exams
class ExamIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["mock", "main"]
    section_id: int
    subject_id: int
    exam_date: date
    max_marks: float = Field(gt=0, le=1000)
    pass_marks: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _pass(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name required")
        if self.pass_marks > self.max_marks:
            raise ValueError("pass_marks cannot exceed max_marks")
        return self


class ExamPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    exam_date: date | None = None
    max_marks: float | None = Field(default=None, gt=0, le=1000)
    pass_marks: float | None = Field(default=None, ge=0)


class MyResult(BaseModel):
    marks: float | None
    absent: bool
    percentage: float | None
    passed: bool | None
    remarks: str


class ExamOut(ORM):
    id: int
    name: str
    kind: str
    section_id: int
    subject_id: int
    teacher_id: int
    exam_date: date
    max_marks: float
    pass_marks: float
    status: str
    published_at: datetime | None
    has_paper: bool = False
    has_key: bool = False  # staff only
    entered_count: int | None = None  # staff only
    total_students: int | None = None  # staff only
    my_result: MyResult | None = None  # student / parent-of-child, only once published


class MarkIn(BaseModel):
    student_id: int
    marks: float | None = Field(default=None, ge=0)
    absent: bool = False
    remarks: str = Field(default="", max_length=200)


class MarksIn(BaseModel):
    rows: list[MarkIn] = Field(max_length=500)


class MarkRow(BaseModel):
    student_id: int
    admission_no: str
    full_name: str
    roll_no: int | None
    marks: float | None
    absent: bool
    remarks: str
    percentage: float | None


class ExamStats(BaseModel):
    entered: int
    absent: int
    average: float | None
    highest: float | None
    lowest: float | None
    passed: int
    failed: int


class MarksSheet(BaseModel):
    exam: ExamOut
    rows: list[MarkRow]
    stats: ExamStats


# ---------------------------------------------------------------- report card
class SubjectResult(BaseModel):
    subject_id: int
    subject: str
    main_percentage: float | None
    mock_percentage: float | None
    quiz_percentage: float | None
    grade: str | None  # from main exams only
    exams: list[dict]  # [{name, kind, date, marks, max_marks, percentage, absent}]


class ProgressPoint(BaseModel):
    date: date
    kind: Literal["main", "mock", "quiz"]
    label: str
    subject: str
    percentage: float


class TopicStat(BaseModel):
    topic: str
    correct: int
    total: int
    percentage: float
    weak: bool


class HomeworkSummary(BaseModel):
    total: int
    submitted: int
    reviewed: int
    late: int


class ReportCard(BaseModel):
    student_id: int
    student_name: str
    admission_no: str
    class_name: str
    section_name: str
    roll_no: int | None
    academic_year: str
    subjects: list[SubjectResult]
    overall_percentage: float | None  # mean of per-subject main-exam percentages; mock/quiz are practice only
    overall_grade: str | None
    progress: list[ProgressPoint]
    topics: list[TopicStat]
    homework: HomeworkSummary
