"""School intelligence (Phase 4 analytics):
- Teacher performance dashboard: class/section/subject/topic averages, frequently missed questions, completion %,
  improvement vs previous exam, students needing a check-in, one-click revision quiz from weak topics.
- Admin school intelligence: section/subject averages, attendance, participation, growth over time, AI-style pattern
  detection that suggests INTERVENTIONS (never labels a learner as weak or incapable).
- Parent leave assistant (plain message -> PENDING request, never auto-approved).
- Audit log viewer.

Pattern texts are i18n keys + params, so the UI shows them in the reader's language."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import chitti, kb
from ..assess import aware, pct, section_students
from ..db import get_db
from ..deps import child_ids, require_roles, teacher_of, tenant_id
from ..learn import WEAK_BELOW, topic_counts
from ..models import (
    AttemptAnswer, AttendanceRecord, AttendanceSession, Exam, LeaveApproval, LeaveRequest, Mark, Quiz, QuizAttempt, QuizQuestion, Role,
    SchoolClass, Section, Student, Subject, TeacherAssignment, User,
)  # fmt: skip
from ..models_v2 import AuditLog
from ..notify import admin_user_ids, class_teacher_user_id, notify
from ..schemas_p2 import LEAVE_TYPES
from .structure import get_or_404
from .v2util import teacher_sections

router = APIRouter(tags=["insights"])
staff = require_roles(Role.teacher, Role.admin)
LOW_ATT = 75.0


def _sec_label(db: Session, section_id: int) -> str:
    s = db.scalar(select(Section).where(Section.id == section_id))
    return f"{s.school_class.name}-{s.name}" if s else "?"


def _att(db: Session, student_ids: list[int], since: date | None = None, until: date | None = None) -> dict[int, float]:
    q = select(AttendanceRecord.student_id, AttendanceRecord.status, func.count()).join(AttendanceSession).where(
        AttendanceRecord.student_id.in_(student_ids or [-1]), AttendanceSession.period == 0)  # fmt: skip
    if since:
        q = q.where(AttendanceSession.date >= since)
    if until:
        q = q.where(AttendanceSession.date <= until)
    agg: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for sid_, st, n in db.execute(q.group_by(AttendanceRecord.student_id, AttendanceRecord.status)).all():
        agg[sid_][1] += n
        if st in ("present", "late"):
            agg[sid_][0] += n
    return {k: round(100 * a / t, 1) for k, (a, t) in agg.items() if t}


def _quiz_stats(db: Session, student_ids: list[int], subject_id: int | None = None, since: date | None = None) -> dict[int, dict]:
    q = select(QuizAttempt, Quiz.subject_id).join(Quiz, Quiz.id == QuizAttempt.quiz_id).where(
        QuizAttempt.student_id.in_(student_ids or [-1]), QuizAttempt.status == "graded")  # fmt: skip
    if subject_id:
        q = q.where(Quiz.subject_id == subject_id)
    out: dict[int, dict] = defaultdict(lambda: {"pcts": [], "last": None})
    for a, _subj in db.execute(q.order_by(QuizAttempt.submitted_at)).all():
        if since and a.submitted_at and aware(a.submitted_at).date() < since:
            continue
        p = pct(a.score, a.max_score)
        if p is not None:
            out[a.student_id]["pcts"].append(p)
        out[a.student_id]["last"] = a.submitted_at
    return out


def _exam_avg(db: Session, student_ids: list[int], subject_id: int | None = None) -> dict[int, float]:
    q = select(Mark.student_id, Mark.marks, Exam.max_marks).join(Exam, Exam.id == Mark.exam_id).where(
        Mark.student_id.in_(student_ids or [-1]), Exam.status == "published", Exam.kind == "main", Mark.absent.is_(False), Mark.marks.is_not(None))  # fmt: skip
    if subject_id:
        q = q.where(Exam.subject_id == subject_id)
    agg: dict[int, list[float]] = defaultdict(list)
    for s, m, mx in db.execute(q).all():
        agg[s].append(100 * m / mx)
    return {k: round(sum(v) / len(v), 1) for k, v in agg.items()}


def _mean(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


# ------------------------------------------------------------------ teacher dashboard
@router.get("/insights/teacher")
def teacher_insights(section_id: int, subject_id: int | None = None, user: User = Depends(staff), sid: int = Depends(tenant_id),
                     db: Session = Depends(get_db)):  # fmt: skip
    if user.role == Role.teacher.value and section_id not in teacher_sections(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your section")
    get_or_404(db, Section, section_id, sid)
    studs = section_students(db, sid, section_id)
    ids = [s.id for s in studs]
    att = _att(db, ids)
    qs = _quiz_stats(db, ids, subject_id)
    ex = _exam_avg(db, ids, subject_id)
    tc = topic_counts(db, ids)
    now = datetime.now(timezone.utc)
    quizzes = list(db.scalars(select(Quiz).where(Quiz.school_id == sid, Quiz.section_id == section_id, Quiz.status != "draft",
                                                 *([Quiz.subject_id == subject_id] if subject_id else [])).order_by(Quiz.id)))  # fmt: skip
    students = []
    for s in studs:
        p = qs.get(s.id, {"pcts": [], "last": None})
        avg = _mean(p["pcts"])
        weak = sorted({t for (st, _sub, t), (c, n) in tc.items() if st == s.id and n and 100 * c / n < WEAK_BELOW})
        flags = []
        if s.id in att and att[s.id] < LOW_ATT:
            flags.append("low_attendance")
        if avg is not None and avg < WEAK_BELOW:
            flags.append("needs_support")
        if quizzes and (p["last"] is None or now - aware(p["last"]) > timedelta(days=14)):
            flags.append("stopped_quizzes")
        if len(p["pcts"]) >= 2 and p["pcts"][-1] - p["pcts"][0] >= 15:
            flags.append("improving")
        students.append({"id": s.id, "name": s.user.full_name, "roll_no": s.roll_no, "attendance": att.get(s.id), "quiz_avg": avg,
                         "exam_avg": ex.get(s.id), "attempts": len(p["pcts"]), "weak_topics": weak[:5], "flags": flags})  # fmt: skip
    # quiz table + frequently missed questions
    qrows, missed = [], []
    for q in quizzes:
        atts = list(db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == q.id, QuizAttempt.status != "in_progress")))
        pcts_ = [pct(a.score, a.max_score) for a in atts if a.status == "graded"]
        qrows.append({"id": q.id, "title": q.title, "subject_id": q.subject_id, "avg": _mean(pcts_), "completion": round(100 * len(atts) / len(ids), 1) if ids else 0,
                      "attempts": len(atts), "status": q.status})  # fmt: skip
        for qq in q.questions:
            rows = db.execute(select(AttemptAnswer.is_correct).join(QuizAttempt).where(AttemptAnswer.question_id == qq.id, AttemptAnswer.is_correct.is_not(None))).scalars().all()
            if rows:
                wrong = 100 * sum(1 for r in rows if not r) / len(rows)
                missed.append({"question_id": qq.id, "quiz": q.title, "text": qq.text[:160], "topic": qq.topic, "wrong_pct": round(wrong, 1), "answers": len(rows)})
    missed.sort(key=lambda m: -m["wrong_pct"])
    topics: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (_st, _sub, t), (c, n) in tc.items():
        topics[t][0] += c
        topics[t][1] += n
    topic_rows = sorted([{"topic": t, "mastery": round(100 * c / n, 1), "answers": n} for t, (c, n) in topics.items() if n], key=lambda r: r["mastery"])
    # improvement vs previous main exam (section averages)
    exams = list(db.scalars(select(Exam).where(Exam.section_id == section_id, Exam.status == "published", Exam.kind == "main",
                                              *([Exam.subject_id == subject_id] if subject_id else [])).order_by(Exam.exam_date)))  # fmt: skip
    exam_trend = []
    for e in exams[-6:]:
        ms = [100 * m.marks / e.max_marks for m in db.scalars(select(Mark).where(Mark.exam_id == e.id, Mark.marks.is_not(None)))]
        exam_trend.append({"exam": e.name, "date": e.exam_date, "avg": _mean(ms)})
    improvement = round(exam_trend[-1]["avg"] - exam_trend[-2]["avg"], 1) if len(exam_trend) >= 2 and exam_trend[-1]["avg"] is not None and exam_trend[-2]["avg"] is not None else None
    return {
        "section_id": section_id, "section": _sec_label(db, section_id),
        "summary": {"students": len(ids), "quiz_avg": _mean([s["quiz_avg"] for s in students]), "attendance": _mean(list(att.values())),
                    "completion": _mean([q["completion"] for q in qrows]), "exam_avg": _mean(list(ex.values())), "improvement": improvement,
                    "attention": sum(1 for s in students if {"needs_support", "low_attendance", "stopped_quizzes"} & set(s["flags"]))},
        "students": students, "quizzes": qrows, "missed": missed[:10], "topics": topic_rows, "exam_trend": exam_trend,
    }  # fmt: skip


class RevisionIn(BaseModel):
    section_id: int
    subject_id: int
    topics: list[str] = Field(default_factory=list, max_length=10)
    max_questions: int = Field(10, ge=3, le=30)


@router.post("/insights/revision-quiz", status_code=201)
def revision_quiz(body: RevisionIn, user: User = Depends(require_roles(Role.teacher)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """One click: a DRAFT quiz built from the most-missed questions in weak topics (+ starter-bank items). Teacher reviews, then publishes."""
    t = teacher_of(db, user)
    if not t or not db.scalar(select(TeacherAssignment.id).where(TeacherAssignment.teacher_id == t.id, TeacherAssignment.section_id == body.section_id,
                                                                   TeacherAssignment.subject_id == body.subject_id)):  # fmt: skip
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not teach this subject in this section")
    ids = [s.id for s in section_students(db, sid, body.section_id)]
    tc = topic_counts(db, ids)
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (_s, subj, top), (c, n) in tc.items():
        if subj == body.subject_id:
            agg[top][0] += c
            agg[top][1] += n
    weak = body.topics or [tp for tp, (c, n) in sorted(agg.items(), key=lambda kv: kv[1][0] / max(1, kv[1][1])) if n and 100 * c / n < 70][:4]
    if not weak:
        raise HTTPException(status.HTTP_409_CONFLICT, "No weak topics found yet: students need to attempt some quizzes first")
    pool = []
    for qq in db.scalars(select(QuizQuestion).join(Quiz).where(Quiz.section_id == body.section_id, Quiz.subject_id == body.subject_id,
                                                               QuizQuestion.topic.in_(weak))):  # fmt: skip
        rows = db.execute(select(AttemptAnswer.is_correct).where(AttemptAnswer.question_id == qq.id, AttemptAnswer.is_correct.is_not(None))).scalars().all()
        wrong = sum(1 for r in rows if not r) / len(rows) if rows else 0
        pool.append((wrong, qq))
    pool.sort(key=lambda x: -x[0])
    seen, picked = set(), []
    for _w, qq in pool:
        if qq.text not in seen:
            seen.add(qq.text)
            picked.append(qq)
    quiz = Quiz(school_id=sid, created_by=user.id, section_id=body.section_id, subject_id=body.subject_id, teacher_id=t.id,
                title=f"Revision: {', '.join(weak)[:150]}", description="Auto-built from weak topics. Review before publishing.", status="draft",
                time_limit_minutes=20, source="manual")  # fmt: skip
    db.add(quiz)
    db.flush()
    pos = 0
    for qq in picked[: body.max_questions]:
        db.add(QuizQuestion(school_id=sid, created_by=user.id, quiz_id=quiz.id, position=pos, qtype=qq.qtype, text=qq.text, options=qq.options,
                            answer=qq.answer, explanation=qq.explanation, topic=qq.topic, difficulty=qq.difficulty, marks=qq.marks))  # fmt: skip
        pos += 1
    for tp in weak:  # top up from the starter bank when the section has few questions
        found = kb.find(tp)
        for q in (found[1]["questions"] if found else []):
            if pos >= body.max_questions or q["q"] in seen:
                continue
            db.add(QuizQuestion(school_id=sid, created_by=user.id, quiz_id=quiz.id, position=pos, qtype="mcq", text=q["q"], options=q["o"],
                                answer=q["a"], explanation=q["e"], topic=tp, difficulty="easy", marks=1.0))  # fmt: skip
            pos += 1
    if pos == 0:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "No questions available for those topics yet")
    db.commit()
    return {"quiz_id": quiz.id, "title": quiz.title, "questions": pos, "topics": weak}


# ------------------------------------------------------------------ admin school intelligence
@router.get("/insights/school")
def school_insights(class_id: int | None = None, section_id: int | None = None, subject_id: int | None = None,
                    date_from: date | None = None, date_to: date | None = None, user: User = Depends(require_roles(Role.admin)),
                    sid: int = Depends(tenant_id), db: Session = Depends(get_db)):  # fmt: skip
    secs_q = select(Section).where(Section.school_id == sid)
    if class_id:
        secs_q = secs_q.where(Section.class_id == class_id)
    if section_id:
        secs_q = secs_q.where(Section.id == section_id)
    sections = list(db.scalars(secs_q))
    all_ids: list[int] = []
    sec_rows, patterns = [], []
    for s in sections:
        ids = [x.id for x in section_students(db, sid, s.id)]
        all_ids += ids
        if not ids:
            continue
        att = _att(db, ids, date_from, date_to)
        qs = _quiz_stats(db, ids, subject_id, date_from)
        ex = _exam_avg(db, ids, subject_id)
        quiz_avg = _mean([_mean(v["pcts"]) for v in qs.values()])
        n_quizzes = db.scalar(select(func.count()).select_from(Quiz).where(Quiz.section_id == s.id, Quiz.status != "draft",
                                                                           *([Quiz.subject_id == subject_id] if subject_id else []))) or 0  # fmt: skip
        n_att = db.scalar(select(func.count()).select_from(QuizAttempt).join(Quiz).where(Quiz.section_id == s.id, QuizAttempt.status != "in_progress",
                                                                                         *([Quiz.subject_id == subject_id] if subject_id else []))) or 0  # fmt: skip
        completion = round(100 * n_att / (n_quizzes * len(ids)), 1) if n_quizzes else None
        row = {"section_id": s.id, "section": f"{s.school_class.name}-{s.name}", "students": len(ids), "attendance": _mean(list(att.values())),
               "quiz_avg": quiz_avg, "exam_avg": _mean(list(ex.values())), "completion": completion}  # fmt: skip
        sec_rows.append(row)
        stopped = sum(1 for i in ids if n_quizzes and (i not in qs or not qs[i]["last"] or datetime.now(timezone.utc) - aware(qs[i]["last"]) > timedelta(days=14)))
        if row["attendance"] is not None and row["attendance"] < LOW_ATT:
            patterns.append({"key": "pattern.low_attendance_section", "params": {"section": row["section"], "value": row["attendance"]},
                             "action": "action.attendance_drive", "severity": "high"})  # fmt: skip
        if quiz_avg is not None and quiz_avg < 55:
            patterns.append({"key": "pattern.low_avg_section", "params": {"section": row["section"], "value": quiz_avg},
                             "action": "action.remedial_sessions", "severity": "medium"})  # fmt: skip
        if stopped:
            patterns.append({"key": "pattern.stopped_quizzes", "params": {"section": row["section"], "count": stopped},
                             "action": "action.gentle_checkin", "severity": "medium"})  # fmt: skip
        # attendance-performance: low attenders scoring below their peers
        low = [i for i in ids if att.get(i, 100) < LOW_ATT and qs.get(i) and _mean(qs[i]["pcts"]) is not None]
        if low and quiz_avg is not None:
            gap = quiz_avg - _mean([_mean(qs[i]["pcts"]) for i in low])
            if gap and gap > 10:
                patterns.append({"key": "pattern.attendance_performance", "params": {"section": row["section"], "gap": round(gap, 1)},
                                 "action": "action.attendance_buddy", "severity": "medium"})  # fmt: skip
        improving = sum(1 for i in ids if len(qs.get(i, {"pcts": []})["pcts"]) >= 2 and qs[i]["pcts"][-1] - qs[i]["pcts"][0] >= 15)
        if improving:
            patterns.append({"key": "pattern.improving", "params": {"section": row["section"], "count": improving},
                             "action": "action.celebrate", "severity": "good"})  # fmt: skip
    # subjects
    subj_rows = []
    subjects = list(db.scalars(select(Subject).where(Subject.school_id == sid, *([Subject.id == subject_id] if subject_id else []))))
    for sub in subjects:
        qs = _quiz_stats(db, all_ids, sub.id, date_from)
        ex = _exam_avg(db, all_ids, sub.id)
        qa = _mean([_mean(v["pcts"]) for v in qs.values()])
        if qa is None and not ex:
            continue
        subj_rows.append({"subject_id": sub.id, "subject": sub.name, "quiz_avg": qa, "exam_avg": _mean(list(ex.values()))})
        if qa is not None and qa < 55:
            patterns.append({"key": "pattern.struggling_subject", "params": {"subject": sub.name, "value": qa}, "action": "action.subject_review", "severity": "medium"})
    # topics needing reteaching (school-wide)
    tc = topic_counts(db, all_ids)
    topics: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (_s, subj, t), (c, n) in tc.items():
        if not subject_id or subj == subject_id:
            topics[t][0] += c
            topics[t][1] += n
    reteach = sorted([{"topic": t, "mastery": round(100 * c / n, 1), "answers": n} for t, (c, n) in topics.items() if n >= 3], key=lambda r: r["mastery"])
    for r in reteach[:3]:
        if r["mastery"] < WEAK_BELOW:
            patterns.append({"key": "pattern.reteach_topic", "params": {"topic": r["topic"], "value": r["mastery"]}, "action": "action.reteach", "severity": "high"})
    # growth over time: weekly quiz average (last 8 weeks)
    weeks: dict[str, list[float]] = defaultdict(list)
    for a in db.scalars(select(QuizAttempt).where(QuizAttempt.student_id.in_(all_ids or [-1]), QuizAttempt.status == "graded")):
        if a.submitted_at:
            y, w, _ = aware(a.submitted_at).isocalendar()
            p = pct(a.score, a.max_score)
            if p is not None:
                weeks[f"{y}-W{w:02d}"].append(p)
    growth = [{"week": k, "avg": _mean(v)} for k, v in sorted(weeks.items())][-8:]
    att_all = _att(db, all_ids, date_from, date_to)
    today = date.today()
    today_rows = db.execute(select(AttendanceRecord.status, func.count()).join(AttendanceSession).where(
        AttendanceSession.school_id == sid, AttendanceSession.date == today, AttendanceSession.period == 0).group_by(AttendanceRecord.status)).all()  # fmt: skip
    sev = {"high": 0, "medium": 1, "good": 2}
    return {
        "cards": {"school_avg": _mean([r["quiz_avg"] for r in sec_rows]), "attendance": _mean(list(att_all.values())),
                  "quiz_completion": _mean([r["completion"] for r in sec_rows]), "classes_monitored": len(sec_rows), "students": len(all_ids)},
        "today": dict(today_rows), "sections": sec_rows, "subjects": subj_rows, "reteach": reteach[:8], "growth": growth,
        "patterns": sorted(patterns, key=lambda p: sev.get(p["severity"], 3)),
        "classes": [{"id": c.id, "name": c.name} for c in db.scalars(select(SchoolClass).where(SchoolClass.school_id == sid).order_by(SchoolClass.sort_order))],
    }  # fmt: skip


@router.get("/audit-logs")
def audit_logs(action: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
               user: User = Depends(require_roles(Role.admin)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):  # fmt: skip
    q = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.user_id).where(AuditLog.school_id == sid)
    if action:
        q = q.where(AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.school_id == sid, *([AuditLog.action == action] if action else [])))
    rows = db.execute(q.order_by(AuditLog.id.desc()).offset(offset).limit(limit)).all()
    return {"total": total, "items": [{"id": a.id, "user": n or "", "role": a.role, "action": a.action, "path": a.path, "status": a.status_code,
                                       "detail": a.detail, "at": a.created_at} for a, n in rows]}  # fmt: skip


# ------------------------------------------------------------------ parent leave assistant
class LeaveMsgIn(BaseModel):
    message: str = Field(min_length=3, max_length=1000)


@router.post("/leave-assist/parse")
def leave_parse(body: LeaveMsgIn, user: User = Depends(require_roles(Role.parent)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    kids = [(s.id, s.user.full_name) for s in db.scalars(select(Student).where(Student.id.in_(child_ids(db, user) or {-1})))]
    d = chitti.parse_leave_message(body.message, kids, date.today())
    return {**d, "children": [{"id": i, "name": n} for i, n in kids], "needs_review": d["confidence"] < 0.7 or d["student_id"] is None}


class LeaveSubmitIn(BaseModel):
    student_id: int
    from_date: date
    to_date: date
    leave_type: str
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/leave-assist/submit", status_code=201)
def leave_submit(body: LeaveSubmitIn, user: User = Depends(require_roles(Role.parent)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Creates a PENDING request for the child. The parent's step is recorded (they wrote it), so it goes to the class
    teacher. It is never approved automatically; teacher decides, then the parent is notified."""
    if body.student_id not in child_ids(db, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    if body.leave_type not in LEAVE_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"leave_type must be one of {', '.join(LEAVE_TYPES)}")
    if body.to_date < body.from_date or (body.to_date - body.from_date).days > 59:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Check the dates")
    stu = db.scalar(select(Student).where(Student.id == body.student_id))
    overlap = db.scalar(select(LeaveRequest.id).where(LeaveRequest.applicant_user_id == stu.user_id, LeaveRequest.status.in_(
        ["pending_parent", "pending_teacher", "pending_admin", "approved"]), LeaveRequest.from_date <= body.to_date, LeaveRequest.to_date >= body.from_date))  # fmt: skip
    if overlap:
        raise HTTPException(status.HTTP_409_CONFLICT, "Leave already exists for these dates")
    r = LeaveRequest(school_id=sid, created_by=user.id, applicant_user_id=stu.user_id, applicant_role="student", student_id=stu.id,
                     leave_type=body.leave_type, from_date=body.from_date, to_date=body.to_date, reason=body.reason.strip(), status="pending_teacher")  # fmt: skip
    db.add(r)
    db.flush()
    db.add(LeaveApproval(school_id=sid, created_by=user.id, request_id=r.id, step="parent", approver_user_id=user.id, decision="approved",
                         comment="Submitted by parent via message"))  # fmt: skip
    params = {"name": stu.user.full_name, "from": body.from_date.isoformat(), "to": body.to_date.isoformat()}
    notify(db, sid, [class_teacher_user_id(db, stu.section_id)], "leave", "notif.leave_needs_teacher", params, "leave")
    notify(db, sid, admin_user_ids(db, sid), "leave", "notif.leave_parent_message", params, "leave")
    db.commit()
    return {"id": r.id, "status": r.status}
