"""Demo seed. Usage:  python -m app.seed [--reset]

Logins printed at the end. Data mirrors the vision demo (EN-26-001..008, Class 10-A)."""
import sys
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models_v2  # noqa: F401  (create 2.0 tables too)
from .db import Base, SessionLocal, engine
from .models import (
    AcademicYear, Parent, Period, Role, School, SchoolClass, Section, Student, StudentParent, Subject, Teacher,
    TeacherAssignment, TimetableEntry, User,
)  # fmt: skip
from .routers.people import dob_password, get_or_create_parent, link
from .security import hash_password

SCHOOL_CODE = "EDN01"
STUDENTS = [  # admission_no, name, gender, dob, parent mobile, parent name, relation
    ("EN-26-001", "Aarav Reddy", "M", date(2010, 8, 15), "9000000001", "Suresh Reddy", "Father"),
    ("EN-26-002", "Diya Sharma", "F", date(2010, 3, 22), "9000000002", "Anita Sharma", "Mother"),
    ("EN-26-003", "Kabir Rao", "M", date(2010, 11, 5), "9000000003", "Venkat Rao", "Father"),
    ("EN-26-004", "Meera Nair", "F", date(2010, 1, 30), "9000000004", "Latha Nair", "Mother"),
    ("EN-26-005", "Rohan Das", "M", date(2010, 6, 18), "9000000005", "Amit Das", "Father"),
    ("EN-26-006", "Sana Khan", "F", date(2010, 9, 9), "9000000006", "Farah Khan", "Mother"),
    ("EN-26-007", "Tara Iyer", "F", date(2010, 12, 12), "9000000007", "Meenakshi Iyer", "Mother"),
    ("EN-26-008", "Vihaan Patel", "M", date(2010, 4, 2), "9000000008", "Hiren Patel", "Father"),
]


def reset(db: Session) -> None:
    db.close()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed_demo(db: Session, code: str = SCHOOL_CODE, name: str = "EduNest Demo School") -> School:
    school = School(
        name=name, code=code, address="Plot 12, Jubilee Hills", district="Hyderabad", mandal="Shaikpet",
        default_language="en", headmaster_name="Dr. R. Krishnan", headmaster_phone="9000011111",
    )  # fmt: skip
    db.add(school)
    db.flush()
    sid = school.id
    db.add(AcademicYear(school_id=sid, label="2026-27", start_date=date(2026, 6, 1), end_date=date(2027, 4, 30), is_current=True))
    db.add(User(school_id=sid, role=Role.admin.value, login_id="admin", full_name="School Admin",
                password_hash=hash_password("admin123")))  # fmt: skip

    classes = {n: SchoolClass(school_id=sid, name=n, sort_order=int(n)) for n in ("9", "10")}
    db.add_all(classes.values())
    db.flush()
    secs = {}
    for cname, snames in (("9", ["A"]), ("10", ["A", "B"])):
        for s in snames:
            secs[f"{cname}-{s}"] = Section(school_id=sid, class_id=classes[cname].id, name=s)
    db.add_all(secs.values())
    subs = {n: Subject(school_id=sid, name=n, code=n[:3].upper())
            for n in ("Mathematics", "Science", "English", "Telugu", "Hindi", "Social Studies")}  # fmt: skip
    db.add_all(subs.values())
    db.flush()

    teachers = {}
    for emp, nm, qual in (("T-001", "Mrs. Lakshmi", "M.Sc, B.Ed"), ("T-002", "Mr. Arjun", "M.Sc Physics"),
                          ("T-003", "Ms. Priya", "M.A English")):  # fmt: skip
        u = User(school_id=sid, role=Role.teacher.value, login_id=emp, full_name=nm,
                 phone="98000" + emp[-3:] + "00", password_hash=hash_password("teacher123"))  # demo: no forced change
        db.add(u)
        db.flush()
        t = Teacher(school_id=sid, user_id=u.id, employee_id=emp, qualification=qual, joining_date=date(2020, 6, 1))
        db.add(t)
        db.flush()
        teachers[emp] = t
    secs["10-A"].class_teacher_id = teachers["T-001"].id
    secs["10-B"].class_teacher_id = teachers["T-002"].id
    secs["9-A"].class_teacher_id = teachers["T-003"].id
    for emp, sub, sec in (("T-001", "Mathematics", "10-A"), ("T-001", "Mathematics", "10-B"), ("T-002", "Science", "10-A"),
                          ("T-002", "Science", "10-B"), ("T-003", "English", "10-A"), ("T-003", "English", "9-A"),
                          ("T-001", "Mathematics", "9-A")):  # fmt: skip
        db.add(TeacherAssignment(school_id=sid, teacher_id=teachers[emp].id, subject_id=subs[sub].id, section_id=secs[sec].id))

    # periods + a Mon-Sat timetable for 10-A (teachers only where an assignment exists -> no clashes, all valid)
    pdefs = [(1, "Period 1", time(9, 0), time(9, 45), False), (2, "Period 2", time(9, 45), time(10, 30), False),
             (3, "Break", time(10, 30), time(10, 45), True), (4, "Period 3", time(10, 45), time(11, 30), False),
             (5, "Period 4", time(11, 30), time(12, 15), False), (6, "Lunch", time(12, 15), time(13, 0), True),
             (7, "Period 5", time(13, 0), time(13, 45), False), (8, "Period 6", time(13, 45), time(14, 30), False)]  # fmt: skip
    periods = [Period(school_id=sid, number=n, label=lb, start_time=a, end_time=b, is_break=br) for n, lb, a, b, br in pdefs]
    db.add_all(periods)
    db.flush()
    teach_for = {"Mathematics": "T-001", "Science": "T-002", "English": "T-003"}
    rotation = ["Mathematics", "Science", "English", "Telugu", "Hindi", "Social Studies"]
    lessons = [p for p in periods if not p.is_break]
    for day in range(6):
        for i, per in enumerate(lessons):
            sub = rotation[(day + i) % len(rotation)]
            emp = teach_for.get(sub)
            db.add(TimetableEntry(school_id=sid, section_id=secs["10-A"].id, day=day, period_id=per.id, subject_id=subs[sub].id,
                                  teacher_id=teachers[emp].id if emp else None, room=f"R-{10 + i}"))  # fmt: skip

    def add_student(adm, nm, gender, dob, mobile, pname, rel, cls, sec, roll):
        u = User(school_id=sid, role=Role.student.value, login_id=adm, full_name=nm,
                 password_hash=hash_password(dob_password(dob)), must_change_password=True)  # fmt: skip
        db.add(u)
        db.flush()
        s = Student(school_id=sid, user_id=u.id, admission_no=adm, class_id=classes[cls].id, section_id=secs[sec].id,
                    roll_no=roll, dob=dob, gender=gender, parent_mobile=mobile, address="Hyderabad")  # fmt: skip
        db.add(s)
        db.flush()
        p = get_or_create_parent(db, sid, mobile, pname, rel, 0)
        link(db, sid, s.id, p.id)

    for i, row in enumerate(STUDENTS, 1):
        add_student(*row, "10", "10-A", i)
    # sibling in 9-A shares Aarav's parent -> multi-child parent login demo
    add_student("EN-26-009", "Ishaan Reddy", "M", date(2011, 5, 20), "9000000001", "Suresh Reddy", "Father", "9", "9-A", 1)
    db.commit()
    return school


def ensure_demo_data() -> None:
    """Idempotent: seed the demo school + superadmin only when the DB has no demo school yet (used at startup when
    EDUNEST_SEED_DEMO=1, e.g. on a host whose SQLite file is wiped on every restart)."""
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(School).where(School.code == SCHOOL_CODE)):
            return
        db.add(User(school_id=None, role=Role.superadmin.value, login_id="super", full_name="Platform Admin",
                    password_hash=hash_password("super12345")))  # fmt: skip
        school = seed_demo(db)
        from .seed_v2 import seed_v2

        seed_v2(db, school)


def main() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if "--reset" in sys.argv:
        reset(db)
        db = SessionLocal()
    if db.scalar(select(School).where(School.code == SCHOOL_CODE)):
        print("Already seeded (use --reset to rebuild)")
        return
    db.add(User(school_id=None, role=Role.superadmin.value, login_id="super", full_name="Platform Admin",
                password_hash=hash_password("super12345")))  # fmt: skip
    school = seed_demo(db)
    if "--no-demo-activity" not in sys.argv:
        from .seed_v2 import seed_v2

        seed_v2(db, school)  # illustrative 2.0 data: attendance history, quizzes, XP, library, transport ...
    print(f"""
Seeded school code: {SCHOOL_CODE}
  superadmin  super        / super12345   (no school code)
  admin       admin        / admin123
  teacher     T-001        / teacher123   (also T-002, T-003)
  student     EN-26-001    / 15082010     (DOB DDMMYYYY, must change on first login; EN-26-001..009)
  parent      9000000001   / OTP 000000   (2 children); 9000000002..8 have 1 child each
  counsellor  T-003 (Ms. Priya) can open the counselling inbox
  Demo activity data is ILLUSTRATIVE (relative to today). Use --no-demo-activity for a clean school.
""")


if __name__ == "__main__":
    main()
