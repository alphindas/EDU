"""Quizzes: teacher builds (manual, or AI-drafted from a PDF via the LLM interface), publishes; student takes it with
auto-grading of objective types; descriptive answers wait for the teacher. One attempt per student per quiz.
Students never receive the answer key until they have submitted."""
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import files
from ..assess import assert_assigned, aware, pct, section_students
from ..db import get_db
from ..deps import child_ids, current_user, require_roles, student_of, teacher_of, tenant_id
from ..llm import get_generator, pdf_text
from ..models import AttemptAnswer, Quiz, QuizAttempt, QuizQuestion, Role, Section, Student, Subject, User
from ..notify import notify, student_user_id
from ..schemas_p3 import (
    AnswerResult, AttemptBrief, AttemptPlay, AttemptResult, AttemptRow, GradeIn, QuestionIn, QuestionPlay, QuizDetail, QuizIn,
    QuizOut, SubmitIn,
)
from .structure import get_or_404

router = APIRouter(tags=["quizzes"])
teacher_only = require_roles(Role.teacher)
student_only = require_roles(Role.student)
staff = require_roles(Role.admin, Role.teacher)
GRACE = timedelta(seconds=60)  # network slack on top of the time limit


# ------------------------------------------------------------------ access
def _owner_or_admin(db: Session, user: User, q: Quiz) -> None:
    if user.role == Role.admin.value:
        return
    if user.role == Role.teacher.value and (t := teacher_of(db, user)) and t.id == q.teacher_id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the teacher who made this quiz or admin")


def _can_view(db: Session, user: User, q: Quiz) -> None:
    if user.role in (Role.admin.value, Role.teacher.value):
        return _owner_or_admin(db, user, q)
    if q.status == "draft":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")  # drafts are invisible to students/parents
    if user.role == Role.student.value and (me := student_of(db, user)) and me.section_id == q.section_id:
        return
    if user.role == Role.parent.value:
        kids = child_ids(db, user)
        if kids and db.scalar(select(Student.id).where(Student.id.in_(kids), Student.section_id == q.section_id).limit(1)):
            return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this quiz")


def _brief(a: QuizAttempt | None) -> AttemptBrief | None:
    return AttemptBrief.model_validate(a) if a else None


def _out(db: Session, sid: int, q: Quiz, my: QuizAttempt | None = None, staff_view: bool = False, detail: bool = False) -> QuizOut:
    cls = QuizDetail if detail else QuizOut
    o = cls.model_validate(q)
    o.question_count = len(q.questions)
    o.total_marks = sum(x.marks for x in q.questions)
    o.my_attempt = _brief(my)
    if staff_view:
        o.attempt_count = db.scalar(select(func.count()).select_from(QuizAttempt).where(
            QuizAttempt.quiz_id == q.id, QuizAttempt.status != "in_progress")) or 0  # fmt: skip
        o.pending_grading = db.scalar(select(func.count()).select_from(AttemptAnswer).join(
            QuizAttempt, QuizAttempt.id == AttemptAnswer.attempt_id).where(
            QuizAttempt.quiz_id == q.id, AttemptAnswer.is_correct.is_(None))) or 0  # fmt: skip
    return o


def _set_questions(db: Session, sid: int, quiz: Quiz, items: list[QuestionIn]) -> None:
    quiz.questions = [
        QuizQuestion(school_id=sid, position=i, qtype=x.qtype, text=x.text, options=x.options, answer=x.answer,
                     explanation=x.explanation, topic=x.topic, difficulty=x.difficulty, marks=x.marks)
        for i, x in enumerate(items, 1)
    ]  # fmt: skip


# ------------------------------------------------------------------ authoring
@router.post("/quizzes", response_model=QuizDetail, status_code=201)
def create_quiz(body: QuizIn, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    get_or_404(db, Section, body.section_id, sid)
    get_or_404(db, Subject, body.subject_id, sid)
    t = assert_assigned(db, sid, teacher_of(db, user), body.section_id, body.subject_id)
    quiz = Quiz(school_id=sid, created_by=user.id, section_id=body.section_id, subject_id=body.subject_id, teacher_id=t.id,
                title=body.title, description=body.description, time_limit_minutes=body.time_limit_minutes)  # fmt: skip
    _set_questions(db, sid, quiz, body.questions)
    db.add(quiz)
    db.commit()
    return _out(db, sid, quiz, staff_view=True, detail=True)


@router.post("/quizzes/from-pdf", response_model=QuizDetail, status_code=201)
def quiz_from_pdf(
    file: UploadFile = File(...), section_id: int = Form(...), subject_id: int = Form(...), title: str = Form("", max_length=200),
    time_limit_minutes: int | None = Form(None, ge=1, le=300),
    user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    """PDF -> draft quiz via the LLM interface (currently the offline stub parser). Always lands as a DRAFT for review."""
    get_or_404(db, Section, section_id, sid)
    get_or_404(db, Subject, subject_id, sid)
    t = assert_assigned(db, sid, teacher_of(db, user), section_id, subject_id)
    generator = get_generator()  # 501 early if a provider is configured but missing
    rel, _, name = files.save_upload(sid, "quiz-sources", file, files.DOC)
    try:
        from pathlib import Path

        from ..config import get_settings

        text = pdf_text(str(Path(get_settings().upload_dir) / rel))
        if not text.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No text found in this PDF (scanned PDFs need OCR, not available yet)")
        drafts = []
        for d in generator.generate(text):
            try:
                drafts.append(QuestionIn(**asdict(d)))
            except ValidationError:
                continue  # a malformed draft is dropped; the teacher can add it by hand
        if not drafts:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No questions could be extracted from this PDF")
    except Exception:
        files.remove(rel)
        raise
    quiz = Quiz(school_id=sid, created_by=user.id, section_id=section_id, subject_id=subject_id, teacher_id=t.id,
                title=(title.strip() or name.rsplit(".", 1)[0])[:200], time_limit_minutes=time_limit_minutes, source="pdf",
                source_file=rel)  # fmt: skip
    _set_questions(db, sid, quiz, drafts)
    db.add(quiz)
    db.commit()
    return _out(db, sid, quiz, staff_view=True, detail=True)


@router.put("/quizzes/{qid}", response_model=QuizDetail)
def update_quiz(qid: int, body: QuizIn, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    quiz = get_or_404(db, Quiz, qid, sid)
    _owner_or_admin(db, user, quiz)
    if db.scalar(select(func.count()).select_from(QuizAttempt).where(QuizAttempt.quiz_id == qid)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Students have already started this quiz; it can no longer be edited")
    if (body.section_id, body.subject_id) != (quiz.section_id, quiz.subject_id):
        get_or_404(db, Section, body.section_id, sid)
        get_or_404(db, Subject, body.subject_id, sid)
        assert_assigned(db, sid, teacher_of(db, user), body.section_id, body.subject_id)
        quiz.section_id, quiz.subject_id = body.section_id, body.subject_id
    quiz.title, quiz.description, quiz.time_limit_minutes = body.title, body.description, body.time_limit_minutes
    _set_questions(db, sid, quiz, body.questions)
    db.commit()
    return _out(db, sid, quiz, staff_view=True, detail=True)


@router.post("/quizzes/{qid}/publish", response_model=QuizOut)
def publish_quiz(qid: int, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    quiz = get_or_404(db, Quiz, qid, sid)
    _owner_or_admin(db, user, quiz)
    if quiz.status == "published":
        return _out(db, sid, quiz, staff_view=True)
    if not quiz.questions:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Add at least one question before publishing")
    bad = [str(x.position) for x in quiz.questions if x.qtype != "descriptive" and x.answer in (None, [], "")]
    if bad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Set the correct answer for question(s): {', '.join(bad)}")
    quiz.status = "published"
    notify(db, sid, [student_user_id(db, s.id) for s in section_students(db, sid, quiz.section_id)], "quiz", "notif.quiz_published",
           {"title": quiz.title}, "quizzes")  # fmt: skip
    db.commit()
    return _out(db, sid, quiz, staff_view=True)


@router.post("/quizzes/{qid}/close", response_model=QuizOut)
def close_quiz(qid: int, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    quiz = get_or_404(db, Quiz, qid, sid)
    _owner_or_admin(db, user, quiz)
    if quiz.status != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a published quiz can be closed")
    quiz.status = "closed"
    db.commit()
    return _out(db, sid, quiz, staff_view=True)


@router.delete("/quizzes/{qid}", status_code=204)
def delete_quiz(qid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    quiz = get_or_404(db, Quiz, qid, sid)
    _owner_or_admin(db, user, quiz)
    attempts = db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == qid)).all()
    for a in attempts:
        db.delete(a)  # cascades to answers
    db.flush()
    src = quiz.source_file
    db.delete(quiz)
    db.commit()
    files.remove(src)
    return Response(status_code=204)


# ------------------------------------------------------------------ listing / detail
@router.get("/quizzes", response_model=list[QuizOut])
def list_quizzes(
    section_id: int | None = None, subject_id: int | None = None, child_id: int | None = None,
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    q = select(Quiz).where(Quiz.school_id == sid)
    viewer: Student | None = None
    if user.role == Role.teacher.value:
        t = teacher_of(db, user)
        q = q.where(Quiz.teacher_id == (t.id if t else -1))
    elif user.role == Role.student.value:
        viewer = student_of(db, user)
        q = q.where(Quiz.section_id == (viewer.section_id if viewer else -1), Quiz.status != "draft")
    elif user.role == Role.parent.value:
        if child_id is None or child_id not in child_ids(db, user):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "child_id of one of your children is required")
        viewer = get_or_404(db, Student, child_id, sid)
        q = q.where(Quiz.section_id == viewer.section_id, Quiz.status != "draft")
    elif user.role != Role.admin.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
    if section_id is not None and user.role in (Role.admin.value, Role.teacher.value):
        q = q.where(Quiz.section_id == section_id)
    if subject_id is not None:
        q = q.where(Quiz.subject_id == subject_id)
    rows = db.scalars(q.order_by(Quiz.id.desc()).limit(limit)).all()
    mine: dict[int, QuizAttempt] = {}
    if viewer and rows:
        mine = {a.quiz_id: a for a in db.scalars(select(QuizAttempt).where(
            QuizAttempt.student_id == viewer.id, QuizAttempt.quiz_id.in_([x.id for x in rows])))}  # fmt: skip
    return [_out(db, sid, x, mine.get(x.id), staff_view=viewer is None) for x in rows]


@router.get("/quizzes/{qid}", response_model=QuizDetail)
def get_quiz(qid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Full quiz WITH the answer key: staff only. Students take it through POST /quizzes/{id}/attempts."""
    quiz = get_or_404(db, Quiz, qid, sid)
    _owner_or_admin(db, user, quiz)
    return _out(db, sid, quiz, staff_view=True, detail=True)


# ------------------------------------------------------------------ taking + grading
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().casefold())


def grade_answer(q: QuizQuestion, ans) -> tuple[bool | None, float | None]:
    """-> (is_correct, marks). (None, None) = descriptive answer waiting for the teacher."""
    if q.qtype == "mcq":
        ok = isinstance(ans, int) and not isinstance(ans, bool) and ans == q.answer
    elif q.qtype == "true_false":
        ok = isinstance(ans, bool) and ans == q.answer
    elif q.qtype == "fill_blank":
        ok = isinstance(ans, str) and _norm(ans) in {_norm(a) for a in (q.answer or [])}
    else:  # descriptive
        if isinstance(ans, str) and ans.strip():
            return None, None
        return False, 0.0  # left blank: nothing to grade
    return ok, (q.marks if ok else 0.0)


def _recompute(a: QuizAttempt) -> None:
    a.score = round(sum(x.marks_awarded or 0 for x in a.answers), 2)
    a.status = "submitted" if any(x.is_correct is None for x in a.answers) else "graded"


def _play(quiz: Quiz, a: QuizAttempt) -> AttemptPlay:
    started = aware(a.started_at)
    return AttemptPlay(
        attempt_id=a.id, quiz_id=quiz.id, title=quiz.title, started_at=started,
        deadline=started + timedelta(minutes=quiz.time_limit_minutes) if quiz.time_limit_minutes else None,
        questions=[QuestionPlay.model_validate(x) for x in quiz.questions],
    )  # fmt: skip


@router.post("/quizzes/{qid}/attempts", response_model=AttemptPlay, status_code=201)
def start_attempt(qid: int, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    quiz = get_or_404(db, Quiz, qid, sid)
    me = student_of(db, user)
    if not me or me.section_id != quiz.section_id or quiz.status == "draft":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    a = db.scalar(select(QuizAttempt).where(QuizAttempt.quiz_id == qid, QuizAttempt.student_id == me.id))
    if a:
        if a.status != "in_progress":
            raise HTTPException(status.HTTP_409_CONFLICT, "You have already taken this quiz")
        return _play(quiz, a)  # resume: the clock keeps running from the first start
    if quiz.status != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "This quiz is closed")
    a = QuizAttempt(school_id=sid, created_by=user.id, quiz_id=qid, student_id=me.id, started_at=datetime.now(timezone.utc),
                    max_score=sum(x.marks for x in quiz.questions))  # fmt: skip
    db.add(a)
    db.commit()
    return _play(quiz, a)


def _result(db: Session, sid: int, a: QuizAttempt) -> AttemptResult:
    quiz = get_or_404(db, Quiz, a.quiz_id, sid)
    stu = get_or_404(db, Student, a.student_id, sid)
    by_q = {x.question_id: x for x in a.answers}
    rows = []
    for q in quiz.questions:
        x = by_q.get(q.id)
        rows.append(AnswerResult(
            answer_id=x.id if x else 0, question_id=q.id, qtype=q.qtype, text=q.text, options=q.options, marks=q.marks,
            topic=q.topic, your_answer=x.answer if x else None, correct_answer=q.answer,
            is_correct=x.is_correct if x else False, marks_awarded=x.marks_awarded if x else 0.0,
            explanation=q.explanation, feedback=x.feedback if x else "",
        ))  # fmt: skip
    return AttemptResult(
        id=a.id, quiz_id=quiz.id, quiz_title=quiz.title, student_id=stu.id, student_name=stu.user.full_name, status=a.status,
        score=a.score, max_score=a.max_score, percentage=pct(a.score, a.max_score) if a.status == "graded" else None,
        submitted_at=a.submitted_at, timed_out=a.timed_out, answers=rows,
    )  # fmt: skip


@router.post("/attempts/{aid}/submit", response_model=AttemptResult)
def submit_attempt(aid: int, body: SubmitIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    a = get_or_404(db, QuizAttempt, aid, sid)
    me = student_of(db, user)
    if not me or me.id != a.student_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your attempt")
    if a.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")
    quiz = get_or_404(db, Quiz, a.quiz_id, sid)
    now = datetime.now(timezone.utc)
    a.submitted_at = now
    qs = {q.id: q for q in quiz.questions}
    unknown = [x.question_id for x in body.answers if x.question_id not in qs]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown question id(s): {unknown}")
    given = {x.question_id: x.answer for x in body.answers}
    if quiz.time_limit_minutes and now > aware(a.started_at) + timedelta(minutes=quiz.time_limit_minutes) + GRACE:
        a.timed_out, given = True, {}  # too late: the attempt is closed with whatever the server holds (nothing is autosaved)
    for q in quiz.questions:
        ans = given.get(q.id)
        ok, marks = grade_answer(q, ans)
        a.answers.append(AttemptAnswer(school_id=sid, created_by=user.id, question_id=q.id, answer=ans, is_correct=ok, marks_awarded=marks))
    _recompute(a)
    from .. import gamify  # EduNest 2.0: effort XP for finishing, bonus for accuracy; streak + badges update

    p = pct(a.score, a.max_score) if a.status == "graded" else None
    gamify.safe_award(db, sid, me.id, "quiz", 15 + (int(p // 10) if p is not None else 0), coins=5,
                      world=gamify.subject_world(db, quiz.subject_id), meta={"quiz_id": quiz.id, "pct": p})
    db.commit()
    return _result(db, sid, a)


def _attempt_access(db: Session, user: User, sid: int, aid: int) -> QuizAttempt:
    a = get_or_404(db, QuizAttempt, aid, sid)
    quiz = get_or_404(db, Quiz, a.quiz_id, sid)
    if user.role == Role.student.value:
        me = student_of(db, user)
        if not me or me.id != a.student_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your attempt")
    elif user.role == Role.parent.value:
        if a.student_id not in child_ids(db, user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your child's attempt")
    else:
        _owner_or_admin(db, user, quiz)
    return a


@router.get("/attempts/{aid}", response_model=AttemptResult)
def get_attempt(aid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    a = _attempt_access(db, user, sid, aid)
    if a.status == "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Not submitted yet")  # answer key stays hidden until then
    return _result(db, sid, a)


@router.get("/quizzes/{qid}/attempts", response_model=list[AttemptRow])
def quiz_attempts(qid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    quiz = get_or_404(db, Quiz, qid, sid)
    _owner_or_admin(db, user, quiz)
    atts = {a.student_id: a for a in db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == qid))}
    return [
        AttemptRow(student_id=s.id, admission_no=s.admission_no, full_name=s.user.full_name, roll_no=s.roll_no,
                   attempt=_brief(atts.get(s.id)), attempt_id=atts[s.id].id if s.id in atts else None)
        for s in section_students(db, sid, quiz.section_id)
    ]  # fmt: skip


@router.patch("/attempts/answers/{answer_id}/grade", response_model=AttemptResult)
def grade_descriptive(answer_id: int, body: GradeIn, user: User = Depends(teacher_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    ans = get_or_404(db, AttemptAnswer, answer_id, sid)
    a = get_or_404(db, QuizAttempt, ans.attempt_id, sid)
    quiz = get_or_404(db, Quiz, a.quiz_id, sid)
    _owner_or_admin(db, user, quiz)
    q = get_or_404(db, QuizQuestion, ans.question_id, sid)
    if q.qtype != "descriptive":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only descriptive answers are graded by hand")
    if a.status == "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Not submitted yet")
    if body.marks > q.marks:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Marks cannot exceed {q.marks:g}")
    was = a.status
    ans.marks_awarded, ans.is_correct, ans.feedback = body.marks, body.marks >= q.marks, body.feedback
    db.flush()
    db.refresh(a)
    _recompute(a)
    if was != "graded" and a.status == "graded":
        notify(db, sid, [student_user_id(db, a.student_id)], "quiz", "notif.quiz_graded", {"title": quiz.title}, "quizzes")
    db.commit()
    return _result(db, sid, a)
