"""Learning logic that is plain rules (no AI call): topic mastery / weak topics, weekly plan, SM-2 spacing.
The AI interface only *writes text* (explanations, cards); what to study and when is decided here."""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import AttemptAnswer, LearningPlan, Quiz, QuizAttempt, QuizQuestion, TopicMastery

WEAK_BELOW = 50.0  # same threshold the report card uses
STRONG_FROM = 80.0
MAX_PLAN_TOPICS = 5


def level_for(mastery: float) -> str:
    return "weak" if mastery < WEAK_BELOW else "strong" if mastery >= STRONG_FROM else "ok"


# ------------------------------------------------------------------ mastery
def topic_counts(db: Session, student_ids: list[int]) -> dict[tuple[int, int, str], list[int]]:
    """{(student_id, subject_id, topic): [correct, total]} from submitted attempts. Descriptive answers still awaiting a
    teacher (is_correct is NULL) are skipped rather than counted wrong."""
    agg: dict[tuple[int, int, str], list[int]] = defaultdict(lambda: [0, 0])
    if not student_ids:
        return agg
    rows = db.execute(
        select(QuizAttempt.student_id, Quiz.subject_id, QuizQuestion.topic, AttemptAnswer.is_correct)
        .join(AttemptAnswer, AttemptAnswer.attempt_id == QuizAttempt.id)
        .join(QuizQuestion, QuizQuestion.id == AttemptAnswer.question_id)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(QuizAttempt.student_id.in_(student_ids), QuizAttempt.status != "in_progress", QuizQuestion.topic != "",
               AttemptAnswer.is_correct.is_not(None))
    ).all()  # fmt: skip
    for stu, subj, topic, ok in rows:
        c = agg[(stu, subj, topic)]
        c[1] += 1
        c[0] += 1 if ok else 0
    return agg


def recompute_mastery(db: Session, school_id: int, student_id: int) -> list[TopicMastery]:
    """Refresh the stored mastery rows for one student from quiz answers and return them, weakest first. Two requests can
    refresh the same student at once (the Learning page does); the loser hits the unique key, rolls back and syncs again."""
    for attempt in (1, 2):
        rows = _sync_mastery(db, school_id, student_id)
        try:
            db.commit()
            return rows
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


def _sync_mastery(db: Session, school_id: int, student_id: int) -> list[TopicMastery]:
    fresh = {(s, t): c for (_, s, t), c in topic_counts(db, [student_id]).items()}
    existing = {(m.subject_id, m.topic): m for m in db.scalars(select(TopicMastery).where(TopicMastery.student_id == student_id))}
    for key, m in existing.items():
        if key not in fresh:
            db.delete(m)
    for (subj, topic), (c, n) in fresh.items():
        m = existing.get((subj, topic))
        if not m:
            m = TopicMastery(school_id=school_id, student_id=student_id, subject_id=subj, topic=topic)
            db.add(m)
            existing[(subj, topic)] = m
        m.correct, m.total, m.mastery = c, n, round(c * 100 / n, 1)
    return sorted((existing[k] for k in fresh), key=lambda m: (m.mastery, m.topic))


# ------------------------------------------------------------------ weekly plan
def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday


def build_plan_items(weak: list[TopicMastery], due_cards: int, has_any_mastery: bool) -> list[dict]:
    """Rules: weakest topics first; each gets a revise slot, then a practice slot two days later (spacing); weak<30% starts with
    easy practice. Flashcard reviews on days 1/3/5 when cards are due. Sunday is rest."""
    items: list[dict] = []

    def add(day: int, kind: str, topic: str = "", subject_id: int | None = None, minutes: int = 20, difficulty: str = "medium"):
        items.append({"id": len(items) + 1, "day": day, "kind": kind, "topic": topic, "subject_id": subject_id,
                      "minutes": minutes, "difficulty": difficulty, "done": False})  # fmt: skip

    if not has_any_mastery:
        add(0, "start", minutes=20)  # nothing to base a plan on yet
    elif not weak:
        add(0, "maintain", minutes=20)
        add(3, "maintain", minutes=20)
    else:
        for i, m in enumerate(weak[:MAX_PLAN_TOPICS]):
            diff = "easy" if m.mastery < 30 else "medium"
            add(i, "revise", m.topic, m.subject_id, 25, diff)
            add(min(i + 2, 5), "practice", m.topic, m.subject_id, 20, diff)
    if due_cards:
        for day in (1, 3, 5):
            add(day, "flashcards", minutes=10)
    add(6, "rest", minutes=0)
    items.sort(key=lambda x: (x["day"], x["id"]))
    for n, it in enumerate(items, 1):
        it["id"] = n
    return items


def merge_done(new_items: list[dict], old_items: list[dict]) -> list[dict]:
    """Keep ticked-off state when a plan is regenerated and the same slot still exists."""
    done = {(o["day"], o["kind"], o["topic"], o["subject_id"]) for o in old_items if o.get("done")}
    for it in new_items:
        it["done"] = (it["day"], it["kind"], it["topic"], it["subject_id"]) in done
    return new_items


def plan_topics(plan: LearningPlan) -> set[tuple[int | None, str]]:
    return {(i["subject_id"], i["topic"]) for i in plan.items if i["kind"] in ("revise", "practice")}


# ------------------------------------------------------------------ SM-2
def sm2(ease: float, interval: int, reps: int, quality: int) -> tuple[float, int, int, bool]:
    """Classic SuperMemo-2. quality 0-5 (<3 = forgot). Returns (ease, interval_days, repetitions, lapsed)."""
    if quality < 3:
        return max(1.3, ease), 1, 0, True  # failed: relearn tomorrow, ease unchanged
    if reps == 0:
        interval = 1
    elif reps == 1:
        interval = 6
    else:
        interval = max(1, round(interval * ease))
    ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return round(ease, 3), interval, reps + 1, False
