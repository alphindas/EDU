"""ILLUSTRATIVE demo data for EduNest 2.0 (labelled as demo everywhere it shows). Dates are relative to today so the
dashboards always look alive: 30 days of attendance, quizzes with attempts, exams, library, XP history, transport..."""
import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import gamify, learn
from .models import (
    AttemptAnswer, AttendanceRecord, AttendanceSession, Exam, Mark, Quiz, QuizAttempt, QuizQuestion, School, SchoolClass, Section,
    Student, Subject, Teacher, User,
)  # fmt: skip
from .models_v2 import (
    Announcement, BrainAttempt, EnglishSession, ForumPost, ForumReply, PortfolioItem, Project, Resource, StaffFlag, StudentPrefs,
    StudentTransport, TransportRoute, Vehicle, XpEvent,
)  # fmt: skip
from .routers.content import split_chapters

QUIZZES = [
    ("Mathematics", "Fractions check-up", [
        ("What is 1/2 + 1/4?", ["2/6", "3/4", "1/6"], 1, "Fractions"), ("Simplify 6/9", ["2/3", "3/6", "1/3"], 0, "Fractions"),
        ("Solve: 2x + 3 = 11", ["4", "7", "5"], 0, "Linear equations"), ("Solve: 3x = 21", ["18", "7", "24"], 1, "Linear equations"),
        ("Area of a 5 × 3 rectangle?", ["8", "15", "16"], 1, "Area and perimeter")]),
    ("Science", "Light & the Solar System", [
        ("Which planet is the Red Planet?", ["Venus", "Mars", "Jupiter"], 1, "Solar system"),
        ("A straw looks bent in water due to…", ["Reflection", "Refraction", "Dispersion"], 1, "Light"),
        ("Angle of incidence equals…", ["Angle of reflection", "90°", "Angle of refraction"], 0, "Light"),
        ("Which gas do plants take in?", ["Oxygen", "Carbon dioxide", "Nitrogen"], 1, "Photosynthesis"),
        ("Largest planet?", ["Saturn", "Jupiter", "Earth"], 1, "Solar system")]),
    ("English", "Tenses & Nouns", [
        ("Past tense of 'go'", ["goed", "went", "gone"], 1, "Tenses"), ("'She ___ to school daily.'", ["go", "goes", "going"], 1, "Tenses"),
        ("Pick the proper noun", ["city", "Ganga", "river"], 1, "Nouns"), ("A ___ of fish", ["herd", "school", "pack"], 1, "Nouns")]),
]
SKILL_LUCK = {"EN-26-001": 0.8, "EN-26-002": 0.9, "EN-26-003": 0.45, "EN-26-004": 0.75, "EN-26-005": 0.55, "EN-26-006": 0.85,
              "EN-26-007": 0.65, "EN-26-008": 0.5, "EN-26-009": 0.7}  # fmt: skip

NOTES_LIGHT = """Chapter 1 Light: Reflection
Light is a form of energy that helps us see. Light travels in straight lines. When light falls on a smooth shiny surface like a mirror, it bounces back. This is called reflection.
The angle of incidence is always equal to the angle of reflection. A plane mirror forms an image that is upright, the same size as the object, and laterally inverted.

Chapter 2 Light: Refraction
Refraction is the bending of light when it passes from one medium to another, for example from air into water. That is why a pencil in a glass of water looks bent.
A convex lens converges light rays and is used in magnifying glasses. A concave lens diverges light rays.

Chapter 3 Our Solar System
The Sun and the eight planets that go around it form the Solar System. Mars is called the Red Planet because of iron oxide on its surface.
Jupiter is the largest planet. Venus is the hottest planet because its thick carbon dioxide atmosphere traps heat."""

SYLLABUS_SCI = """Chapter 1 Chemical Reactions and Equations
Balancing equations, types of reactions: combination, decomposition, displacement.
Chapter 2 Acids, Bases and Salts
Indicators, pH scale, neutralisation, salts in daily life.
Chapter 3 Light – Reflection and Refraction
Laws of reflection, mirrors, refraction, lenses, power of a lens.
Chapter 4 Electricity
Current, potential difference, Ohm's law, resistance, series and parallel circuits."""

PAPER_MATHS = """Chapter 1 Section A (1 mark each)
1. Solve 2x + 5 = 17. 2. Find the HCF of 24 and 36. 3. What is 15% of 200?
Chapter 2 Section B (3 marks each)
4. Prove that the sum of angles of a triangle is 180°. 5. A ladder 13 m long reaches a window 12 m high. How far is its foot from the wall?
Chapter 3 Solutions
1. x = 6. 2. 12. 3. 30. 5. Using Pythagoras: √(169 − 144) = 5 m."""


def _aware(d: date, h: int = 10) -> datetime:
    return datetime.combine(d, time(h, 0), tzinfo=timezone.utc)


def seed_v2(db: Session, school: School) -> None:
    sid = school.id
    rnd = random.Random(42)
    today = date.today()
    students = {s.admission_no: s for s in db.scalars(select(Student).where(Student.school_id == sid))}
    teachers = {t.employee_id: t for t in db.scalars(select(Teacher).where(Teacher.school_id == sid))}
    subs = {s.name: s for s in db.scalars(select(Subject).where(Subject.school_id == sid))}
    classes = {c.name: c for c in db.scalars(select(SchoolClass).where(SchoolClass.school_id == sid))}
    secs = {f"{s.school_class.name}-{s.name}": s for s in db.scalars(select(Section).where(Section.school_id == sid))}
    admin = db.scalar(select(User).where(User.school_id == sid, User.role == "admin"))
    s10a = [s for k, s in sorted(students.items()) if s.section_id == secs["10-A"].id]

    # consent (one student left without, to demo the parent-consent flow) + counsellor + prefs/teams
    for adm, s in students.items():
        db.add(StudentPrefs(school_id=sid, student_id=s.id, ai_consent=adm != "EN-26-008", leaderboard_opt_in=adm in ("EN-26-001", "EN-26-002", "EN-26-006"),
                            team=gamify.TEAMS[s.id % 4], avatar={}, ai_consent_at=datetime.now(timezone.utc)))  # fmt: skip
    db.add(StaffFlag(school_id=sid, user_id=teachers["T-003"].user_id, counsellor=True))

    # 30 school days of whole-day attendance for 10-A (EN-26-005 and EN-26-008 attend less)
    d = today - timedelta(days=42)
    days = 0
    while d < today and days < 30:
        if d.weekday() < 6:
            sess = AttendanceSession(school_id=sid, section_id=secs["10-A"].id, date=d, period=0, marked_by=teachers["T-001"].user_id)
            db.add(sess)
            db.flush()
            for s in s10a:
                p_abs = 0.3 if s.admission_no in ("EN-26-005", "EN-26-008") else 0.05
                r = rnd.random()
                st = "absent" if r < p_abs else ("late" if r < p_abs + 0.05 else "present")
                db.add(AttendanceRecord(school_id=sid, session_id=sess.id, student_id=s.id, status=st))
            days += 1
        d += timedelta(days=1)

    # quizzes with attempts spread over the last 4 weeks (EN-26-008 stopped taking quizzes; EN-26-003 is improving)
    teach_for = {"Mathematics": teachers["T-001"], "Science": teachers["T-002"], "English": teachers["T-003"]}
    for qi, (sub, title, qs) in enumerate(QUIZZES):
        for round_ in range(2):
            quiz = Quiz(school_id=sid, section_id=secs["10-A"].id, subject_id=subs[sub].id, teacher_id=teach_for[sub].id,
                        title=f"{title}{' (week ' + str(round_ + 1) + ')' if round_ else ''}", status="published", time_limit_minutes=15,
                        description="Demo quiz")  # fmt: skip
            db.add(quiz)
            db.flush()
            qobjs = []
            for pos, (text, opts, ans, topic) in enumerate(qs):
                q = QuizQuestion(school_id=sid, quiz_id=quiz.id, position=pos, qtype="mcq", text=text, options=opts, answer=ans, topic=topic,
                                 explanation=f"The correct answer is {opts[ans]}.", marks=1.0)  # fmt: skip
                db.add(q)
                qobjs.append(q)
            db.flush()
            day = today - timedelta(days=24 - qi * 3 - round_ * 10)
            for s in s10a:
                if s.admission_no == "EN-26-008" and round_ == 1:
                    continue
                luck = SKILL_LUCK.get(s.admission_no, 0.6) + (0.25 if s.admission_no == "EN-26-003" and round_ == 1 else 0)
                att = QuizAttempt(school_id=sid, quiz_id=quiz.id, student_id=s.id, started_at=_aware(day), submitted_at=_aware(day, 11), status="graded")
                db.add(att)
                db.flush()
                score = 0
                for q in qobjs:
                    ok = rnd.random() < luck
                    given = q.answer if ok else (q.answer + 1) % len(q.options)
                    db.add(AttemptAnswer(school_id=sid, attempt_id=att.id, question_id=q.id, answer=given, is_correct=ok, marks_awarded=1.0 if ok else 0.0))
                    score += 1 if ok else 0
                att.score, att.max_score = float(score), float(len(qobjs))
                pct = round(100 * score / len(qobjs), 1)
                db.add(XpEvent(school_id=sid, student_id=s.id, kind="quiz", xp=15 + int(pct // 10), coins=5, day=day,
                               world=gamify.subject_world(db, subs[sub].id), meta={"quiz_id": quiz.id, "pct": pct}))  # fmt: skip

    # two published MAIN maths exams (improvement visible) + one upcoming
    for n, (name, ago) in enumerate((("Unit Test 1", 35), ("Unit Test 2", 7))):
        ex = Exam(school_id=sid, name=name, kind="main", section_id=secs["10-A"].id, subject_id=subs["Mathematics"].id, teacher_id=teachers["T-001"].id,
                  exam_date=today - timedelta(days=ago), max_marks=50, pass_marks=18, status="published", published_at=datetime.now(timezone.utc))  # fmt: skip
        db.add(ex)
        db.flush()
        for s in s10a:
            base = SKILL_LUCK.get(s.admission_no, 0.6) * 50
            db.add(Mark(school_id=sid, exam_id=ex.id, student_id=s.id, marks=round(min(50, base + rnd.uniform(-5, 5) + n * 3))))
    db.add(Exam(school_id=sid, name="Half-yearly Science", kind="main", section_id=secs["10-A"].id, subject_id=subs["Science"].id,
                teacher_id=teachers["T-002"].id, exam_date=today + timedelta(days=9), max_marks=80, pass_marks=28))  # fmt: skip

    # library
    for kind, title, cls, sub, text, extra in (
        ("notes", "Light & Solar System — class notes", "10", "Science", NOTES_LIGHT, {}),
        ("syllabus", "Class 10 Science syllabus 2026-27", "10", "Science", SYLLABUS_SCI, {}),
        ("paper", "Maths unit test paper + solutions", "10", "Mathematics", PAPER_MATHS, {"year": today.year - 1, "institution": "EduNest Demo School"}),
        ("video", "Water cycle animation (YouTube search)", None, "Science", "",
         {"url": "https://www.youtube.com/results?search_query=water+cycle+for+kids"}),
        ("ebook", "Free textbooks portal (NCERT)", None, None, "", {"url": "https://ncert.nic.in/textbook.php", "description": "Official textbooks"}),
    ):  # fmt: skip
        r = Resource(school_id=sid, created_by=teachers["T-002"].user_id, kind=kind, title=title, class_id=classes[cls].id if cls else None,
                     subject_id=subs[sub].id if sub else None, text=text, chapters=split_chapters(text), **extra)  # fmt: skip
        db.add(r)

    # announcements
    for title, body, aud, emoji, pin in (
        ("Science Exhibition on Friday! 🔬", "Bring your projects to the hall by 9 AM. Parents are welcome from 11 AM.", "all", "🔬", True),
        ("Half-yearly exams timetable", "The half-yearly exam schedule is now in the Exams section.", "students", "📅", False),
        ("Parent–teacher meeting", "PTM this Saturday 10 AM – 1 PM. Book a slot with your class teacher.", "parents", "🤝", False),
    ):  # fmt: skip
        db.add(Announcement(school_id=sid, created_by=admin.id, author_user_id=admin.id, title=title, body=body, audience=aud, emoji=emoji, pinned=pin))

    # gamification history (14 days), brain games, badges, streaks
    for adm, s in students.items():
        if adm == "EN-26-008":
            continue
        luck = SKILL_LUCK.get(adm, 0.6)
        for back in range(13, -1, -1):
            day = today - timedelta(days=back)
            if rnd.random() < 0.25 and back > 6:  # recent week unbroken -> a visible streak in the demo
                continue
            gamify.award(db, sid, s.id, "checkin", 5, coins=2, today=day)  # builds a real streak + badges
            for _ in range(rnd.randint(1, 4)):
                sk = rnd.choice(["logical", "numerical", "pattern", "memory", "problem", "spatial", "verbal", "critical"])
                ok = rnd.random() < luck
                dif = rnd.randint(1, 3)
                db.add(BrainAttempt(school_id=sid, student_id=s.id, skill=sk, difficulty=dif, correct=ok, time_ms=rnd.randint(4000, 30000),
                                    nonce=f"seed{rnd.getrandbits(48):x}"))  # fmt: skip
                db.add(XpEvent(school_id=sid, student_id=s.id, kind="brain", xp=(3 + 2 * dif) if ok else 1, coins=1 if ok else 0, day=day,
                               world=gamify.skill_world(sk)))  # fmt: skip
        db.flush()
    for adm in ("EN-26-001", "EN-26-002"):
        for i, (txt, sc) in enumerate((("i goes to school by bus", 62), ("I go to school by bus every morning.", 81), ("Yesterday I visited my grandmother.", 90))):
            db.add(EnglishSession(school_id=sid, student_id=students[adm].id, kind="grammar", text=txt, words=len(txt.split()), score=sc))

    # community
    aarav, diya = students["EN-26-001"], students["EN-26-002"]
    p = ForumPost(school_id=sid, author_user_id=diya.user_id, section_id=secs["10-A"].id, subject_id=subs["Science"].id, kind="doubt",
                  title="Why does a spoon look bent in water?", body="I saw this at lunch. Is it magic? 😄", likes=[aarav.user_id])  # fmt: skip
    db.add(p)
    db.flush()
    db.add(ForumReply(school_id=sid, post_id=p.id, author_user_id=aarav.user_id, body="It's refraction! Light bends when it goes from water to air.", accepted=True))
    db.add(ForumPost(school_id=sid, author_user_id=aarav.user_id, section_id=None, kind="idea", title="Idea: a school vegetable garden 🌱",
                     body="We could grow tomatoes and learn about photosynthesis for real!", likes=[]))  # fmt: skip
    db.add(Project(school_id=sid, owner_user_id=aarav.user_id, title="Solar oven from a pizza box", summary="Cook s'mores with sunlight! Need 2 more members.",
                   category="science", status="open", members=[aarav.user_id], emoji="☀️"))  # fmt: skip
    db.add(Project(school_id=sid, owner_user_id=diya.user_id, title="Kannada–Telugu word game app", summary="Paper prototype of a language game.",
                   category="coding", status="building", members=[diya.user_id, students["EN-26-006"].user_id], emoji="🎮"))  # fmt: skip
    db.add(PortfolioItem(school_id=sid, student_id=aarav.id, kind="sports", title="Inter-school chess — 2nd place", details="Demo entry", achieved_on=today - timedelta(days=60)))
    db.add(PortfolioItem(school_id=sid, student_id=aarav.id, kind="certificate", title="Science Olympiad participation", details="Demo entry"))

    # transport (Hyderabad demo coordinates)
    route = TransportRoute(school_id=sid, name="Route 1 · Jubilee Hills", start_time="07:30", stops=[
        {"name": "Film Nagar", "lat": 17.4126, "lng": 78.4071, "minute": 0}, {"name": "Road No. 36", "lat": 17.4295, "lng": 78.4107, "minute": 10},
        {"name": "Peddamma Temple", "lat": 17.4339, "lng": 78.4163, "minute": 18}, {"name": "Madhapur Junction", "lat": 17.4416, "lng": 78.3920, "minute": 30},
        {"name": "EduNest School", "lat": 17.4483, "lng": 78.3915, "minute": 40}])  # fmt: skip
    db.add(route)
    db.flush()
    db.add(Vehicle(school_id=sid, route_id=route.id, number="TS09 EA 2026", driver_name="Ramesh (demo)", driver_phone="9000022222", capacity=40,
                   device_token="demo-device-token-change-me"))  # fmt: skip
    for adm, stop in (("EN-26-001", "Road No. 36"), ("EN-26-009", "Road No. 36"), ("EN-26-002", "Film Nagar"), ("EN-26-004", "Peddamma Temple")):
        db.add(StudentTransport(school_id=sid, student_id=students[adm].id, route_id=route.id, stop_name=stop))

    db.flush()
    for s in students.values():
        learn.recompute_mastery(db, sid, s.id)
    db.commit()
