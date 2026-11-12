"""Phase 4 request/response models: robo assistant, practice, AI chat, mastery, weekly plan, flashcards."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["en", "te", "hi"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- robo + practice
class PracticeQuestion(BaseModel):
    """A question WITHOUT its answer key; the key comes back only from the check endpoint."""

    question_id: int
    qtype: str
    text: str
    options: list[str]
    topic: str
    marks: float


class RoboIn(BaseModel):
    answer_id: int
    mode: Literal["explain", "why_wrong", "next"]
    lang: Lang = "en"
    exclude: list[int] = Field(default_factory=list, max_length=50)  # practice question ids already shown (mode=next)


class RoboOut(BaseModel):
    mode: str
    text: str
    provider: str
    cached: bool = False
    practice: PracticeQuestion | None = None


class PracticeCheckIn(BaseModel):
    answer: int | bool | str | None = None


class PracticeCheckOut(BaseModel):
    is_correct: bool
    correct_answer: object
    explanation: str


# ---------------------------------------------------------------- chat
class AiMessageOut(ORM):
    id: int
    role: str
    content: str
    sources: list
    attachment_id: int | None
    provider: str
    created_at: datetime


class ConversationOut(ORM):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[AiMessageOut]


class ConversationIn(BaseModel):
    title: str = Field(default="", max_length=120)


class DocumentOut(ORM):
    id: int
    name: str
    content_type: str
    chunk_count: int
    readable: bool = True  # False = no text could be extracted (image / scanned PDF)
    created_at: datetime


class ChatTurnOut(BaseModel):
    user_message: AiMessageOut
    assistant_message: AiMessageOut
    document: DocumentOut | None = None


# ---------------------------------------------------------------- mastery / plan
class MasteryOut(BaseModel):
    subject_id: int
    subject: str
    topic: str
    correct: int
    total: int
    mastery: float
    level: Literal["weak", "ok", "strong"]


class MasteryReport(BaseModel):
    student_id: int
    topics: list[MasteryOut]
    weak_count: int


class PlanItem(BaseModel):
    id: int
    day: int
    kind: Literal["revise", "practice", "flashcards", "maintain", "start", "rest"]
    topic: str
    subject_id: int | None
    subject: str = ""
    minutes: int
    difficulty: Literal["easy", "medium"]
    done: bool


class PlanOut(BaseModel):
    id: int
    student_id: int
    week_start: date
    items: list[PlanItem]
    stale: bool  # weak topics changed since this plan was made
    due_cards: int


class PlanItemIn(BaseModel):
    done: bool


class GapStudent(BaseModel):
    student_id: int
    name: str
    mastery: float


class GapTopic(BaseModel):
    subject_id: int
    subject: str
    topic: str
    students_attempted: int
    weak_students: int
    avg_mastery: float
    weak_list: list[GapStudent]


class GapReport(BaseModel):
    section_id: int
    topics: list[GapTopic]


# ---------------------------------------------------------------- flashcards
class FlashcardIn(BaseModel):
    front: str = Field(min_length=1, max_length=1000)
    back: str = Field(min_length=1, max_length=2000)
    topic: str = Field(default="", max_length=100)
    subject_id: int | None = None


class FlashcardOut(ORM):
    id: int
    subject_id: int | None
    topic: str
    front: str
    back: str
    source: str
    ease: float
    interval_days: int
    repetitions: int
    lapses: int
    due_date: date
    last_reviewed: date | None


class FlashcardGenIn(BaseModel):
    source: Literal["mistakes", "notes"]
    document_id: int | None = None  # required for notes
    topic: str = Field(default="", max_length=100)  # optional filter for mistakes
    lang: Lang = "en"


class FlashcardGenOut(BaseModel):
    created: int
    skipped_duplicates: int
    cards: list[FlashcardOut]


class ReviewIn(BaseModel):
    quality: int = Field(ge=0, le=5)  # 0-2 forgot, 3 hard, 4 good, 5 easy


class FlashcardStats(BaseModel):
    total: int
    due: int
    new: int
    learned: int  # interval >= 21 days
