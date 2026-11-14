"""EduNest 2.0 schema: CHITTI consent, gamification, knowledge growth, content library, announcements, communication,
projects/portfolio, career, English coach, personal growth, transport and audit logs.

Every school-owned table uses TenantMixin so the tenant guard in db.py applies automatically."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import TenantMixin, utcnow


# ------------------------------------------------------------------ consent + preferences
class StudentPrefs(TenantMixin, Base):
    """Per-student settings. ai_consent is given by a parent; leaderboard visibility is opt-in by the student."""

    __tablename__ = "student_prefs"
    __table_args__ = (UniqueConstraint("student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    ai_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_consent_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # parent user id
    ai_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leaderboard_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar: Mapped[dict] = mapped_column(JSON, default=dict)  # CHITTI buddy look: {color, hat, badge}
    team: Mapped[str] = mapped_column(String(20), default="")  # house team for team battles


class StaffFlag(TenantMixin, Base):
    """Extra staff capabilities. counsellor = may read the counselling inbox."""

    __tablename__ = "staff_flags"
    __table_args__ = (UniqueConstraint("user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    counsellor: Mapped[bool] = mapped_column(Boolean, default=False)


# ------------------------------------------------------------------ gamification
class XpEvent(TenantMixin, Base):
    """One reward. kind: quiz | homework | flashcard | brain | checkin | quest | reflection | english | boss | mystery | project."""

    __tablename__ = "xp_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    world: Mapped[str] = mapped_column(String(20), default="")  # science | math | language | innovation | brain
    xp: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    day: Mapped[date] = mapped_column(Date, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class UserBadge(TenantMixin, Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("student_id", "badge"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    badge: Mapped[str] = mapped_column(String(40))


class Streak(TenantMixin, Base):
    __tablename__ = "streaks"
    __table_args__ = (UniqueConstraint("student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    current: Mapped[int] = mapped_column(Integer, default=0)
    best: Mapped[int] = mapped_column(Integer, default=0)
    last_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    freezes: Mapped[int] = mapped_column(Integer, default=1)  # one missed day forgiven, earned back weekly


class QuestClaim(TenantMixin, Base):
    """A finished daily quest whose reward was claimed (quests themselves are generated from the date)."""

    __tablename__ = "quest_claims"
    __table_args__ = (UniqueConstraint("student_id", "day", "quest"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    quest: Mapped[str] = mapped_column(String(40))


class ShopPurchase(TenantMixin, Base):
    """Knowledge coins spent on CHITTI buddy accessories (cosmetic only)."""

    __tablename__ = "shop_purchases"
    __table_args__ = (UniqueConstraint("student_id", "item"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    item: Mapped[str] = mapped_column(String(40))
    cost: Mapped[int] = mapped_column(Integer)


# ------------------------------------------------------------------ knowledge growth (cognitive skills)
class BrainAttempt(TenantMixin, Base):
    """One answered skill puzzle. skill: logical | numerical | pattern | memory | problem | spatial | verbal | critical."""

    __tablename__ = "brain_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    skill: Mapped[str] = mapped_column(String(12), index=True)
    difficulty: Mapped[int] = mapped_column(Integer)  # 1..5
    correct: Mapped[bool] = mapped_column(Boolean)
    time_ms: Mapped[int] = mapped_column(Integer, default=0)
    nonce: Mapped[str] = mapped_column(String(32), index=True)  # puzzle token nonce: one answer per puzzle


# ------------------------------------------------------------------ content library + announcements
class Resource(TenantMixin, Base):
    """kind: syllabus | notes | textbook | paper | ebook | video | audio. Text is extracted for search + CHITTI."""

    __tablename__ = "resources"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"), nullable=True, index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)  # previous-year papers
    institution: Mapped[str] = mapped_column(String(120), default="")
    chapters: Mapped[list] = mapped_column(JSON, default=list)  # [{title, text}] chapter-wise reading
    text: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(300), default="")
    content_type: Mapped[str] = mapped_column(String(80), default="")
    original_name: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    approved: Mapped[bool] = mapped_column(Boolean, default=True)  # school-approved -> preferred by CHITTI


class ResourceProgress(TenantMixin, Base):
    __tablename__ = "resource_progress"
    __table_args__ = (UniqueConstraint("resource_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    completed_chapters: Mapped[list] = mapped_column(JSON, default=list)
    bookmarks: Mapped[list] = mapped_column(JSON, default=list)  # [{chapter, note}]


class Announcement(TenantMixin, Base):
    """audience: all | students | teachers | parents | staff. section_id narrows to one section."""

    __tablename__ = "announcements"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(10), default="all")
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id"), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    emoji: Mapped[str] = mapped_column(String(8), default="📢")
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


# ------------------------------------------------------------------ communication
class DirectMessage(TenantMixin, Base):
    """Teacher <-> student / teacher <-> parent chat. Allowed pairs are enforced in the router."""

    __tablename__ = "direct_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class ForumPost(TenantMixin, Base):
    """Peer doubt board. kind: doubt | idea | showcase. hidden = removed by a teacher (moderation)."""

    __tablename__ = "forum_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id"), nullable=True, index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(10), default="doubt")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    likes: Mapped[list] = mapped_column(JSON, default=list)  # user ids


class ForumReply(TenantMixin, Base):
    __tablename__ = "forum_replies"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("forum_posts.id"), index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)


class CounsellingThread(TenantMixin, Base):
    """Student -> counsellor. anonymous hides the student's identity from staff. Only counsellors (StaffFlag) read it."""

    __tablename__ = "counselling_threads"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic: Mapped[str] = mapped_column(String(20), default="talk")  # talk | complaint | study_stress | friends | other
    anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | closed


class CounsellingMessage(TenantMixin, Base):
    __tablename__ = "counselling_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("counselling_threads.id"), index=True)
    from_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    staff_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)


# ------------------------------------------------------------------ projects + portfolio
class Project(TenantMixin, Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), default="science")  # science | coding | art | social | robotics | other
    status: Mapped[str] = mapped_column(String(12), default="open")  # open (accepting members) | building | done
    max_members: Mapped[int] = mapped_column(Integer, default=4)
    members: Mapped[list] = mapped_column(JSON, default=list)  # user ids (includes owner)
    emoji: Mapped[str] = mapped_column(String(8), default="🚀")


class ProjectComment(TenantMixin, Base):
    __tablename__ = "project_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)


class PortfolioItem(TenantMixin, Base):
    """kind: certificate | sports | art | project | award | other."""

    __tablename__ = "portfolio_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str] = mapped_column(Text, default="")
    achieved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    file_path: Mapped[str] = mapped_column(String(300), default="")
    content_type: Mapped[str] = mapped_column(String(80), default="")
    original_name: Mapped[str] = mapped_column(String(200), default="")


# ------------------------------------------------------------------ career + english + personal growth
class CareerResult(TenantMixin, Base):
    __tablename__ = "career_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    answers: Mapped[dict] = mapped_column(JSON)
    scores: Mapped[dict] = mapped_column(JSON)  # interest area -> 0..100
    suggestions: Mapped[list] = mapped_column(JSON)


class EnglishSession(TenantMixin, Base):
    """One English Chitti practice. Private to the student (no public ranking)."""

    __tablename__ = "english_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # grammar | speaking | pronounce | interview
    text: Mapped[str] = mapped_column(Text)
    words: Mapped[int] = mapped_column(Integer, default=0)
    wpm: Mapped[float] = mapped_column(Float, default=0.0)
    fillers: Mapped[int] = mapped_column(Integer, default=0)
    issues: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100 fluency/accuracy blend


class Reflection(TenantMixin, Base):
    """Daily reflection / growth mission. Voluntary, private to the student. mood is a simple emoji, never analysed."""

    __tablename__ = "reflections"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(12), default="reflection")  # reflection | mission | scenario
    prompt: Mapped[str] = mapped_column(String(80), default="")
    mood: Mapped[str] = mapped_column(String(8), default="")
    text: Mapped[str] = mapped_column(Text, default="")


# ------------------------------------------------------------------ transport
class TransportRoute(TenantMixin, Base):
    __tablename__ = "transport_routes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    stops: Mapped[list] = mapped_column(JSON, default=list)  # [{name, lat, lng, minute}] minute = offset from start
    start_time: Mapped[str] = mapped_column(String(5), default="07:30")


class Vehicle(TenantMixin, Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey("transport_routes.id"), nullable=True, index=True)
    number: Mapped[str] = mapped_column(String(20))
    driver_name: Mapped[str] = mapped_column(String(100), default="")
    driver_phone: Mapped[str] = mapped_column(String(20), default="")
    capacity: Mapped[int] = mapped_column(Integer, default=40)
    device_token: Mapped[str] = mapped_column(String(64), default="")  # GPS device posts with this token


class VehicleLocation(TenantMixin, Base):
    __tablename__ = "vehicle_locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class StudentTransport(TenantMixin, Base):
    __tablename__ = "student_transport"
    __table_args__ = (UniqueConstraint("student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("transport_routes.id"))
    stop_name: Mapped[str] = mapped_column(String(100), default="")


# ------------------------------------------------------------------ audit
class AuditLog(TenantMixin, Base):
    """Every mutating API call (method, path, status) + AI interactions. school_id NULL for platform-level calls."""

    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True, nullable=True)  # type: ignore[assignment]
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(12), default="")
    action: Mapped[str] = mapped_column(String(10))  # POST | PUT | PATCH | DELETE | AI
    path: Mapped[str] = mapped_column(String(300))
    status_code: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")
