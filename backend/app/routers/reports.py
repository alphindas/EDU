"""Report card + progress graph for one student. Main exams drive the grade; mock exams and quizzes are practice and
appear on the graph and per-subject columns only. Only PUBLISHED exams and fully graded quizzes are counted."""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..assess import grade_for, pct
from ..db import get_db
from ..deps import child_ids, current_user, student_of, teacher_of, tenant_id
from ..models import (
    AcademicYear, AttemptAnswer, Exam, Homework, HomeworkSubmission, Mark, Quiz, QuizAttempt, QuizQuestion, Role, SchoolClass,
    Section, Student, Subject, TeacherAssignment, User,
)  # fmt: skip
from ..schemas_p3 import HomeworkSummary, ProgressPoint, ReportCard, SubjectResult, TopicStat
from .structure import get_or_404

router = APIRouter(tags=["report-card"])
WEAK_BELOW = 50.0  # topic correct-rate (%) under which a topic is flagged weak


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 1) if xs else None


def _may_view(db: Session, user: User, stu: Student) -> None:
    if user.role == Role.admin.value:
        return
    if user.role == Role.student.value:
        me = student_of(db, user)
        if me and me.id == stu.id:
            return
    elif user.role == Role.parent.value:
        if stu.id in child_ids(db, user):
            return
    elif user.role == Role.teacher.value and (t := teacher_of(db, user)):
        sec = db.get(Section, stu.section_id)
        if (sec and sec.class_teacher_id == t.id) or db.scalar(select(TeacherAssignment.id).where(
            TeacherAssignment.teacher_id == t.id, TeacherAssignment.section_id == stu.section_id).limit(1)):  # fmt: skip
            return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this report card")


@router.get("/report-card", response_model=ReportCard)
def report_card(student_id: int | None = None, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if student_id is None:
        me = student_of(db, user) if user.role == Role.student.value else None
        if not me:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
        student_id = me.id
    stu = get_or_404(db, Student, student_id, sid)
    _may_view(db, user, stu)

    subjects = {s.id: s.name for s in db.scalars(select(Subject).where(Subject.school_id == sid))}
    per: dict[int, dict] = defaultdict(lambda: {"main": [], "mock": [], "quiz": [], "exams": []})
    points: list[ProgressPoint] = []

    # ---- exams (published only; absent students are listed but never averaged)
    for e, m in db.execute(
        select(Exam, Mark).join(Mark, Mark.exam_id == Exam.id).where(
            Exam.school_id == sid, Exam.section_id == stu.section_id, Exam.status == "published", Mark.student_id == stu.id)
    ):  # fmt: skip
        p = pct(m.marks, e.max_marks)
        per[e.subject_id]["exams"].append({"name": e.name, "kind": e.kind, "date": e.exam_date.isoformat(), "marks": m.marks,
                                           "max_marks": e.max_marks, "percentage": p, "absent": m.absent})  # fmt: skip
        if p is not None and not m.absent:
            per[e.subject_id][e.kind].append(p)
            points.append(ProgressPoint(date=e.exam_date, kind=e.kind, label=e.name, subject=subjects.get(e.subject_id, ""), percentage=p))

    # ---- quizzes (only fully graded attempts; pending descriptive answers would understate the score)
    for a, qz in db.execute(
        select(QuizAttempt, Quiz).join(Quiz, Quiz.id == QuizAttempt.quiz_id).where(
            QuizAttempt.school_id == sid, QuizAttempt.student_id == stu.id, QuizAttempt.status == "graded")
    ):  # fmt: skip
        p = pct(a.score, a.max_score)
        if p is None or a.submitted_at is None:
            continue
        per[qz.subject_id]["quiz"].append(p)
        points.append(ProgressPoint(date=a.submitted_at.date(), kind="quiz", label=qz.title, subject=subjects.get(qz.subject_id, ""), percentage=p))
    points.sort(key=lambda x: x.date)

    rows = []
    for subj_id, d in per.items():
        main = _mean(d["main"])
        rows.append(SubjectResult(subject_id=subj_id, subject=subjects.get(subj_id, "—"), main_percentage=main,
                                  mock_percentage=_mean(d["mock"]), quiz_percentage=_mean(d["quiz"]), grade=grade_for(main),
                                  exams=sorted(d["exams"], key=lambda x: x["date"])))  # fmt: skip
    rows.sort(key=lambda r: r.subject)
    overall = _mean([r.main_percentage for r in rows if r.main_percentage is not None])

    # ---- topic analysis from quiz answers
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for q, ans in db.execute(
        select(QuizQuestion, AttemptAnswer).join(AttemptAnswer, AttemptAnswer.question_id == QuizQuestion.id)
        .join(QuizAttempt, QuizAttempt.id == AttemptAnswer.attempt_id)
        .where(QuizAttempt.student_id == stu.id, QuizAttempt.status != "in_progress", QuizQuestion.topic != "", AttemptAnswer.is_correct.is_not(None))
    ):  # fmt: skip
        agg[q.topic][1] += 1
        agg[q.topic][0] += 1 if ans.is_correct else 0
    topics = sorted(
        (TopicStat(topic=t, correct=c, total=n, percentage=round(c * 100 / n, 1), weak=c * 100 / n < WEAK_BELOW) for t, (c, n) in agg.items()),
        key=lambda x: x.percentage,
    )  # fmt: skip

    # ---- homework completion
    hw_total = db.scalar(select(func.count()).select_from(Homework).where(Homework.school_id == sid, Homework.section_id == stu.section_id)) or 0
    subs = db.scalars(select(HomeworkSubmission).where(HomeworkSubmission.student_id == stu.id)).all()
    homework = HomeworkSummary(total=hw_total, submitted=len(subs), reviewed=sum(1 for s in subs if s.status == "reviewed"),
                               late=sum(1 for s in subs if s.is_late))  # fmt: skip

    cls, sec = db.get(SchoolClass, stu.class_id), db.get(Section, stu.section_id)
    year = db.scalar(select(AcademicYear.label).where(AcademicYear.school_id == sid, AcademicYear.is_current.is_(True))) or ""
    return ReportCard(
        student_id=stu.id, student_name=stu.user.full_name, admission_no=stu.admission_no, class_name=cls.name if cls else "",
        section_name=sec.name if sec else "", roll_no=stu.roll_no, academic_year=year, subjects=rows, overall_percentage=overall,
        overall_grade=grade_for(overall), progress=points, topics=topics, homework=homework,
    )  # fmt: skip
