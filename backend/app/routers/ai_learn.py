"""Phase 4 learning loop: robo assistant on wrong quiz answers, practice questions, weak-topic mastery, weekly plan,
spaced-repetition flashcards, teacher learning-gap report.

Answer-key safety: a student only ever gets the key of a question once they have submitted the quiz it belongs to (same rule
as the quiz result screen), so practice/check endpoints are limited to questions from the student's own submitted quizzes."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import learn
from ..ai import Tutor, WrongAnswerCtx, get_tutor
from ..ai_usage import charge
from ..assess import section_students
from ..db import get_db
from ..deps import current_user, require_roles, student_of, teacher_of, tenant_id
from ..models import (
    AiDocument, AttemptAnswer, Flashcard, LearningPlan, Quiz, QuizAttempt, QuizQuestion, RoboHelp, Role, Section, Student, Subject,
    TeacherAssignment, User,
)  # fmt: skip
from ..schemas_p4 import (
    FlashcardGenIn, FlashcardGenOut, FlashcardIn, FlashcardOut, FlashcardStats, GapReport, GapStudent, GapTopic, MasteryOut,
    MasteryReport, PlanItemIn, PlanOut, PracticeCheckIn, PracticeCheckOut, PracticeQuestion, ReviewIn, RoboIn, RoboOut,
)  # fmt: skip
from .quizzes import grade_answer
from .reports import _may_view
from .structure import get_or_404

router = APIRouter(prefix="/ai", tags=["ai-learning"])
student_only = require_roles(Role.student)
DIFF = {"easy": 0, "medium": 1, "hard": 2}


def _me(db: Session, user: User) -> Student:
    me = student_of(db, user)
    if not me:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Student account required")
    return me


def _render(q: QuizQuestion, v) -> str:
    """A stored answer as plain text for the tutor / for flashcards."""
    if v is None or v == "":
        return ""
    if q.qtype == "mcq":
        return q.options[v] if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(q.options) else str(v)
    if q.qtype == "true_false":
        return "True" if v is True else "False" if v is False else str(v)
    if isinstance(v, list):
        return " / ".join(str(x) for x in v)
    return str(v)


def _practice_q(q: QuizQuestion) -> PracticeQuestion:
    return PracticeQuestion(question_id=q.id, qtype=q.qtype, text=q.text, options=q.options, topic=q.topic, marks=q.marks)


def _practice_pool(db: Session, sid: int, stu: Student, *, topic: str, subject_id: int | None, quiz_id: int | None = None,
                   exclude: set[int] = frozenset()) -> list[QuizQuestion]:  # type: ignore[assignment]
    """Auto-gradable questions from quizzes the student has already submitted; mistakes first, then easier, then oldest."""
    done = select(QuizAttempt.quiz_id).where(QuizAttempt.student_id == stu.id, QuizAttempt.status != "in_progress")
    stmt = (select(QuizQuestion).join(Quiz, Quiz.id == QuizQuestion.quiz_id)
            .where(QuizQuestion.school_id == sid, QuizQuestion.quiz_id.in_(done), QuizQuestion.qtype != "descriptive",
                   QuizQuestion.answer.is_not(None)))  # fmt: skip
    if topic:
        stmt = stmt.where(QuizQuestion.topic == topic)
    elif quiz_id:
        stmt = stmt.where(QuizQuestion.quiz_id == quiz_id)
    if subject_id:
        stmt = stmt.where(Quiz.subject_id == subject_id)
    if exclude:
        stmt = stmt.where(QuizQuestion.id.not_in(exclude))
    pool = list(db.scalars(stmt))
    wrong = set(db.scalars(select(AttemptAnswer.question_id).join(QuizAttempt, QuizAttempt.id == AttemptAnswer.attempt_id)
                           .where(QuizAttempt.student_id == stu.id, AttemptAnswer.is_correct.is_(False))))  # fmt: skip
    return sorted(pool, key=lambda q: (q.id not in wrong, DIFF.get(q.difficulty, 1), q.id))


# ------------------------------------------------------------------ robo assistant
@router.post("/robo", response_model=RoboOut)
def robo(body: RoboIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
         tutor: Tutor = Depends(get_tutor)):  # fmt: skip
    me = _me(db, user)
    ans = get_or_404(db, AttemptAnswer, body.answer_id, sid)
    att = get_or_404(db, QuizAttempt, ans.attempt_id, sid)
    if att.student_id != me.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your answer")
    if att.status == "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Submit the quiz first")
    if ans.is_correct is not False:
        raise HTTPException(status.HTTP_409_CONFLICT, "The assistant helps with wrong answers only")
    q = get_or_404(db, QuizQuestion, ans.question_id, sid)

    if body.mode == "next":
        quiz = get_or_404(db, Quiz, q.quiz_id, sid)
        pool = _practice_pool(db, sid, me, topic=q.topic, subject_id=quiz.subject_id, quiz_id=q.quiz_id, exclude=set(body.exclude) | {q.id})
        pick = pool[0] if pool else None
        charge(db, sid, user.id, "robo", tutor.name)
        text = tutor.next_suggestion(q.topic, pick is not None, body.lang)
        db.commit()
        return RoboOut(mode="next", text=text, provider=tutor.name, practice=_practice_q(pick) if pick else None)

    hit = db.scalar(select(RoboHelp).where(RoboHelp.answer_id == ans.id, RoboHelp.mode == body.mode, RoboHelp.lang == body.lang))
    if hit:
        return RoboOut(mode=body.mode, text=hit.text, provider=hit.provider, cached=True)
    ctx = WrongAnswerCtx(question=q.text, qtype=q.qtype, options=list(q.options), correct=_render(q, q.answer), given=_render(q, ans.answer),
                         topic=q.topic, explanation=q.explanation, lang=body.lang)  # fmt: skip
    charge(db, sid, user.id, "robo", tutor.name)
    text = tutor.explain(ctx) if body.mode == "explain" else tutor.why_wrong(ctx)
    db.add(RoboHelp(school_id=sid, created_by=user.id, answer_id=ans.id, mode=body.mode, lang=body.lang, text=text, provider=tutor.name))
    db.commit()
    return RoboOut(mode=body.mode, text=text, provider=tutor.name)


# ------------------------------------------------------------------ practice
@router.get("/practice", response_model=list[PracticeQuestion])
def practice(topic: str = Query(min_length=1, max_length=100), subject_id: int | None = None, limit: int = Query(5, ge=1, le=20),
             exclude: list[int] = Query(default=[]), user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):  # fmt: skip
    me = _me(db, user)
    return [_practice_q(q) for q in _practice_pool(db, sid, me, topic=topic, subject_id=subject_id, exclude=set(exclude))[:limit]]


@router.post("/practice/{qid}/check", response_model=PracticeCheckOut)
def practice_check(qid: int, body: PracticeCheckIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    me = _me(db, user)
    q = get_or_404(db, QuizQuestion, qid, sid)
    submitted = db.scalar(select(QuizAttempt.id).where(QuizAttempt.quiz_id == q.quiz_id, QuizAttempt.student_id == me.id,
                                                       QuizAttempt.status != "in_progress").limit(1))  # fmt: skip
    if not submitted or q.qtype == "descriptive":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")  # not revealing that it exists
    ok, _ = grade_answer(q, body.answer)
    return PracticeCheckOut(is_correct=bool(ok), correct_answer=q.answer, explanation=q.explanation)


# ------------------------------------------------------------------ mastery + plan
def _target(db: Session, user: User, sid: int, student_id: int | None) -> Student:
    if user.role == Role.student.value:
        me = _me(db, user)
        if student_id not in (None, me.id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        return me
    if student_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
    stu = get_or_404(db, Student, student_id, sid)
    _may_view(db, user, stu)  # admin / own child / teacher of that section
    return stu


def _subjects(db: Session, sid: int) -> dict[int, str]:
    return {s.id: s.name for s in db.scalars(select(Subject).where(Subject.school_id == sid))}


@router.get("/mastery", response_model=MasteryReport)
def mastery(student_id: int | None = None, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = _target(db, user, sid, student_id)
    rows = learn.recompute_mastery(db, sid, stu.id)
    names = _subjects(db, sid)
    out = [MasteryOut(subject_id=m.subject_id, subject=names.get(m.subject_id, "—"), topic=m.topic, correct=m.correct, total=m.total,
                      mastery=m.mastery, level=learn.level_for(m.mastery)) for m in rows]  # fmt: skip
    return MasteryReport(student_id=stu.id, topics=out, weak_count=sum(1 for m in out if m.level == "weak"))


def _due_count(db: Session, stu: Student) -> int:
    return db.scalar(select(func.count()).select_from(Flashcard).where(Flashcard.student_id == stu.id, Flashcard.due_date <= date.today())) or 0


def _plan_out(db: Session, sid: int, plan: LearningPlan, weak, stu: Student) -> PlanOut:
    names = _subjects(db, sid)
    current = {(m.subject_id, m.topic) for m in weak[: learn.MAX_PLAN_TOPICS]}
    items = [{**i, "subject": names.get(i["subject_id"], "")} for i in plan.items]
    return PlanOut(id=plan.id, student_id=stu.id, week_start=plan.week_start, items=items, stale=learn.plan_topics(plan) != current,
                   due_cards=_due_count(db, stu))  # fmt: skip


def _make_items(db: Session, stu: Student, rows: list) -> list[dict]:
    weak = [m for m in rows if m.mastery < learn.WEAK_BELOW]
    return learn.build_plan_items(weak, _due_count(db, stu), bool(rows))


@router.get("/plan", response_model=PlanOut)
def get_plan(student_id: int | None = None, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = _target(db, user, sid, student_id)
    rows = learn.recompute_mastery(db, sid, stu.id)
    ws = learn.week_start(date.today())
    find = select(LearningPlan).where(LearningPlan.student_id == stu.id, LearningPlan.week_start == ws)
    plan = db.scalar(find)
    if not plan:
        plan = LearningPlan(school_id=sid, created_by=user.id, student_id=stu.id, week_start=ws, items=_make_items(db, stu, rows))
        db.add(plan)
        try:
            db.commit()
        except IntegrityError:  # a concurrent request created this week's plan first: use theirs
            db.rollback()
            plan = db.scalar(find)
    return _plan_out(db, sid, plan, [m for m in rows if m.mastery < learn.WEAK_BELOW], stu)


@router.post("/plan/regenerate", response_model=PlanOut)
def regenerate_plan(user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = _me(db, user)
    rows = learn.recompute_mastery(db, sid, stu.id)
    ws = learn.week_start(date.today())
    plan = db.scalar(select(LearningPlan).where(LearningPlan.student_id == stu.id, LearningPlan.week_start == ws))
    items = _make_items(db, stu, rows)
    if plan:
        plan.items = learn.merge_done(items, plan.items)
    else:
        plan = LearningPlan(school_id=sid, created_by=user.id, student_id=stu.id, week_start=ws, items=items)
        db.add(plan)
    db.commit()
    return _plan_out(db, sid, plan, [m for m in rows if m.mastery < learn.WEAK_BELOW], stu)


@router.patch("/plan/{plan_id}/items/{item_id}", response_model=PlanOut)
def tick_item(plan_id: int, item_id: int, body: PlanItemIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = _me(db, user)
    plan = get_or_404(db, LearningPlan, plan_id, sid)
    if plan.student_id != stu.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LearningPlan not found")
    if not any(i["id"] == item_id for i in plan.items):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan item not found")
    plan.items = [{**i, "done": body.done} if i["id"] == item_id else i for i in plan.items]  # new list: JSON column change detection
    db.commit()
    rows = learn.recompute_mastery(db, sid, stu.id)
    return _plan_out(db, sid, plan, [m for m in rows if m.mastery < learn.WEAK_BELOW], stu)


# ------------------------------------------------------------------ teacher learning-gap report
@router.get("/gap-report", response_model=GapReport)
def gap_report(section_id: int, user: User = Depends(require_roles(Role.teacher, Role.admin)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    sec = get_or_404(db, Section, section_id, sid)
    subject_filter: set[int] | None = None  # None = all subjects (admin / class teacher)
    if user.role == Role.teacher.value:
        t = teacher_of(db, user)
        taught = set(db.scalars(select(TeacherAssignment.subject_id).where(TeacherAssignment.teacher_id == (t.id if t else -1),
                                                                            TeacherAssignment.section_id == sec.id)))  # fmt: skip
        if not (t and sec.class_teacher_id == t.id) and not taught:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not teach this section")
        if not (t and sec.class_teacher_id == t.id):
            subject_filter = taught
    studs = {s.id: s for s in section_students(db, sid, sec.id)}
    names = _subjects(db, sid)
    by_topic: dict[tuple[int, str], list[tuple[int, float]]] = {}
    for (stu_id, subj, topic), (c, n) in learn.topic_counts(db, list(studs)).items():
        if subject_filter is None or subj in subject_filter:
            by_topic.setdefault((subj, topic), []).append((stu_id, round(c * 100 / n, 1)))
    topics = []
    for (subj, topic), rows in by_topic.items():
        weak = sorted((r for r in rows if r[1] < learn.WEAK_BELOW), key=lambda r: r[1])
        topics.append(GapTopic(
            subject_id=subj, subject=names.get(subj, "—"), topic=topic, students_attempted=len(rows), weak_students=len(weak),
            avg_mastery=round(sum(m for _, m in rows) / len(rows), 1),
            weak_list=[GapStudent(student_id=i, name=studs[i].user.full_name, mastery=m) for i, m in weak],
        ))  # fmt: skip
    topics.sort(key=lambda t: (-t.weak_students, t.avg_mastery, t.topic))
    return GapReport(section_id=sec.id, topics=topics)


# ------------------------------------------------------------------ flashcards (SM-2)
@router.get("/flashcards", response_model=list[FlashcardOut])
def list_cards(due: bool = False, topic: str = "", user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    me = _me(db, user)
    stmt = select(Flashcard).where(Flashcard.student_id == me.id)
    if due:
        stmt = stmt.where(Flashcard.due_date <= date.today())
    if topic:
        stmt = stmt.where(Flashcard.topic == topic)
    return list(db.scalars(stmt.order_by(Flashcard.due_date, Flashcard.id).limit(500)))


@router.get("/flashcards/stats", response_model=FlashcardStats)
def card_stats(user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    me = _me(db, user)
    cards = list(db.scalars(select(Flashcard).where(Flashcard.student_id == me.id)))
    today = date.today()
    return FlashcardStats(total=len(cards), due=sum(1 for c in cards if c.due_date <= today), new=sum(1 for c in cards if c.repetitions == 0 and not c.last_reviewed),
                          learned=sum(1 for c in cards if c.interval_days >= 21))  # fmt: skip


def _check_subject(db: Session, sid: int, subject_id: int | None) -> None:
    if subject_id is not None:
        get_or_404(db, Subject, subject_id, sid)


@router.post("/flashcards", response_model=FlashcardOut, status_code=201)
def create_card(body: FlashcardIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    me = _me(db, user)
    _check_subject(db, sid, body.subject_id)
    c = Flashcard(school_id=sid, created_by=user.id, student_id=me.id, subject_id=body.subject_id, topic=body.topic.strip(),
                  front=body.front.strip(), back=body.back.strip(), source="manual", due_date=date.today())  # fmt: skip
    db.add(c)
    db.commit()
    return c


@router.delete("/flashcards/{cid}", status_code=204)
def delete_card(cid: int, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    me = _me(db, user)
    c = get_or_404(db, Flashcard, cid, sid)
    if c.student_id != me.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flashcard not found")
    db.delete(c)
    db.commit()


@router.post("/flashcards/generate", response_model=FlashcardGenOut)
def generate_cards(body: FlashcardGenIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
                   tutor: Tutor = Depends(get_tutor)):  # fmt: skip
    me = _me(db, user)
    have = {c.front.strip().casefold() for c in db.scalars(select(Flashcard).where(Flashcard.student_id == me.id))}
    drafts: list[tuple[str, str, str, int | None, str]] = []  # front, back, topic, subject_id, source
    if body.source == "mistakes":  # built straight from the student's own wrong answers; no AI text needed
        stmt = (select(QuizQuestion, Quiz.subject_id).join(AttemptAnswer, AttemptAnswer.question_id == QuizQuestion.id)
                .join(QuizAttempt, QuizAttempt.id == AttemptAnswer.attempt_id).join(Quiz, Quiz.id == QuizQuestion.quiz_id)
                .where(QuizAttempt.student_id == me.id, QuizAttempt.status != "in_progress", AttemptAnswer.is_correct.is_(False),
                       QuizQuestion.answer.is_not(None), QuizQuestion.answer != "")
                .order_by(QuizQuestion.id).limit(30))  # fmt: skip
        if body.topic:
            stmt = stmt.where(QuizQuestion.topic == body.topic)
        seen: set[int] = set()
        for q, subj in db.execute(stmt):
            if q.id in seen:
                continue
            seen.add(q.id)
            back = _render(q, q.answer) + (f"\n\n{q.explanation}" if q.explanation else "")
            drafts.append((q.text, back, q.topic, subj, "mistakes"))
    else:
        if not body.document_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "document_id is required for notes")
        doc = get_or_404(db, AiDocument, body.document_id, sid)
        if doc.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "AiDocument not found")
        if not doc.text:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No readable text in this file (images and scanned PDFs need OCR)")
        charge(db, sid, user.id, "flashcards", tutor.name)
        for d in tutor.make_cards(doc.text[:20000], body.topic, 10):  # only academic text leaves, never the user's identity
            drafts.append((d.front, d.back, d.topic, None, "notes"))
    made, dup = [], 0
    for front, back, topic, subj, src in drafts:
        key = front.strip().casefold()
        if key in have:
            dup += 1
            continue
        have.add(key)
        c = Flashcard(school_id=sid, created_by=user.id, student_id=me.id, subject_id=subj, topic=topic[:100], front=front.strip(),
                      back=back.strip(), source=src, due_date=date.today())  # fmt: skip
        db.add(c)
        made.append(c)
    db.commit()
    return FlashcardGenOut(created=len(made), skipped_duplicates=dup, cards=made)


@router.post("/flashcards/{cid}/review", response_model=FlashcardOut)
def review_card(cid: int, body: ReviewIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    me = _me(db, user)
    c = get_or_404(db, Flashcard, cid, sid)
    if c.student_id != me.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Flashcard not found")
    c.ease, c.interval_days, c.repetitions, lapsed = learn.sm2(c.ease, c.interval_days, c.repetitions, body.quality)
    c.lapses += 1 if lapsed else 0
    c.last_reviewed = date.today()
    c.due_date = date.today() + timedelta(days=c.interval_days)
    db.commit()
    return c

