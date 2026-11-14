"""School profile, academic years, classes, sections, subjects, teacher assignments."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require_roles, tenant_id
from ..models import (
    AcademicYear,
    Role,
    School,
    SchoolClass,
    Section,
    Student,
    Subject,
    Teacher,
    TeacherAssignment,
    User,
)
from ..schemas import (
    AcademicYearIn,
    AcademicYearOut,
    AssignmentIn,
    AssignmentOut,
    ClassIn,
    ClassOut,
    SchoolIn,
    SchoolOut,
    SchoolPatch,
    SectionIn,
    SectionOut,
    SectionPatch,
    SubjectIn,
    SubjectOut,
)
from ..security import hash_password

router = APIRouter(tags=["structure"])
admin_only = require_roles(Role.admin)
superadmin_only = require_roles(Role.superadmin)


def conflict(db: Session, msg: str):
    db.rollback()
    raise HTTPException(status.HTTP_409_CONFLICT, msg)


def get_or_404(db: Session, model, obj_id: int, school_id: int):
    obj = db.scalar(select(model).where(model.id == obj_id, model.school_id == school_id))
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return obj


# ---------------------------------------------------------------- schools
@router.post("/schools", response_model=SchoolOut, status_code=201)
def create_school(body: SchoolIn, _: User = Depends(superadmin_only), db: Session = Depends(get_db)):
    data = body.model_dump(exclude={"admin_login", "admin_password", "admin_name"})
    school = School(**data)
    db.add(school)
    try:
        db.flush()
    except IntegrityError:
        conflict(db, "School code already exists")
    db.add(
        User(
            school_id=school.id,
            role=Role.admin.value,
            login_id=body.admin_login,
            full_name=body.admin_name,
            password_hash=hash_password(body.admin_password),
        )
    )
    db.commit()
    return school


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(_: User = Depends(superadmin_only), db: Session = Depends(get_db)):
    return db.scalars(select(School).order_by(School.id)).all()


@router.get("/school", response_model=SchoolOut)
def my_school(sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return db.get(School, sid)


@router.patch("/school", response_model=SchoolOut)
def patch_school(
    body: SchoolPatch, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    school = db.get(School, sid)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(school, k, v)
    db.commit()
    return school


# ---------------------------------------------------------------- academic years
@router.get("/academic-years", response_model=list[AcademicYearOut])
def list_years(_: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return db.scalars(select(AcademicYear).where(AcademicYear.school_id == sid).order_by(AcademicYear.start_date)).all()


@router.post("/academic-years", response_model=AcademicYearOut, status_code=201)
def create_year(
    body: AcademicYearIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    if body.is_current:
        db.execute(update(AcademicYear).where(AcademicYear.school_id == sid).values(is_current=False))
    obj = AcademicYear(school_id=sid, created_by=user.id, **body.model_dump())
    db.add(obj)
    db.commit()
    return obj


# ---------------------------------------------------------------- classes
@router.get("/classes", response_model=list[ClassOut])
def list_classes(_: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return db.scalars(
        select(SchoolClass).where(SchoolClass.school_id == sid).order_by(SchoolClass.sort_order, SchoolClass.name)
    ).all()


@router.post("/classes", response_model=ClassOut, status_code=201)
def create_class(
    body: ClassIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    obj = SchoolClass(school_id=sid, created_by=user.id, **body.model_dump())
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        conflict(db, "Class name already exists")
    return obj


@router.patch("/classes/{cid}", response_model=ClassOut)
def patch_class(
    cid: int, body: ClassIn, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    obj = get_or_404(db, SchoolClass, cid, sid)
    for k, v in body.model_dump().items():
        setattr(obj, k, v)
    try:
        db.commit()
    except IntegrityError:
        conflict(db, "Class name already exists")
    return obj


@router.delete("/classes/{cid}", status_code=204)
def delete_class(cid: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    obj = get_or_404(db, SchoolClass, cid, sid)
    if db.scalar(select(func.count()).select_from(Student).where(Student.class_id == cid, Student.school_id == sid)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Class still has students")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- sections
def _check_teacher(db: Session, teacher_id: int | None, sid: int):
    if teacher_id is not None:
        get_or_404(db, Teacher, teacher_id, sid)


@router.get("/sections", response_model=list[SectionOut])
def list_sections(
    class_id: int | None = None,
    _: User = Depends(current_user),
    sid: int = Depends(tenant_id),
    db: Session = Depends(get_db),
):
    q = select(Section).where(Section.school_id == sid).order_by(Section.class_id, Section.name)
    if class_id:
        q = q.where(Section.class_id == class_id)
    return db.scalars(q).all()


@router.post("/sections", response_model=SectionOut, status_code=201)
def create_section(
    body: SectionIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    get_or_404(db, SchoolClass, body.class_id, sid)
    _check_teacher(db, body.class_teacher_id, sid)
    obj = Section(school_id=sid, created_by=user.id, **body.model_dump())
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        conflict(db, "Section already exists in this class")
    return obj


@router.patch("/sections/{sec_id}", response_model=SectionOut)
def patch_section(
    sec_id: int,
    body: SectionPatch,
    _: User = Depends(admin_only),
    sid: int = Depends(tenant_id),
    db: Session = Depends(get_db),
):
    obj = get_or_404(db, Section, sec_id, sid)
    data = body.model_dump(exclude_unset=True)
    if "class_teacher_id" in data:
        _check_teacher(db, data["class_teacher_id"], sid)
    for k, v in data.items():
        setattr(obj, k, v)
    try:
        db.commit()
    except IntegrityError:
        conflict(db, "Section already exists in this class")
    return obj


@router.delete("/sections/{sec_id}", status_code=204)
def delete_section(
    sec_id: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    obj = get_or_404(db, Section, sec_id, sid)
    if db.scalar(select(func.count()).select_from(Student).where(Student.section_id == sec_id, Student.school_id == sid)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Section still has students")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- subjects
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(_: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return db.scalars(select(Subject).where(Subject.school_id == sid).order_by(Subject.name)).all()


@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(
    body: SubjectIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    obj = Subject(school_id=sid, created_by=user.id, **body.model_dump())
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        conflict(db, "Subject already exists")
    return obj


@router.patch("/subjects/{sub_id}", response_model=SubjectOut)
def patch_subject(
    sub_id: int, body: SubjectIn, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    obj = get_or_404(db, Subject, sub_id, sid)
    for k, v in body.model_dump().items():
        setattr(obj, k, v)
    try:
        db.commit()
    except IntegrityError:
        conflict(db, "Subject already exists")
    return obj


@router.delete("/subjects/{sub_id}", status_code=204)
def delete_subject(
    sub_id: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    obj = get_or_404(db, Subject, sub_id, sid)
    if db.scalar(select(func.count()).select_from(TeacherAssignment).where(TeacherAssignment.subject_id == sub_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Subject is assigned to a teacher")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- teacher assignments
@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(
    teacher_id: int | None = None,
    section_id: int | None = None,
    _: User = Depends(require_roles(Role.admin, Role.teacher)),
    sid: int = Depends(tenant_id),
    db: Session = Depends(get_db),
):
    q = select(TeacherAssignment).where(TeacherAssignment.school_id == sid)
    if teacher_id:
        q = q.where(TeacherAssignment.teacher_id == teacher_id)
    if section_id:
        q = q.where(TeacherAssignment.section_id == section_id)
    return db.scalars(q).all()


@router.post("/assignments", response_model=AssignmentOut, status_code=201)
def create_assignment(
    body: AssignmentIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)
):
    get_or_404(db, Teacher, body.teacher_id, sid)
    get_or_404(db, Section, body.section_id, sid)
    get_or_404(db, Subject, body.subject_id, sid)
    obj = TeacherAssignment(school_id=sid, created_by=user.id, **body.model_dump())
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        conflict(db, "Assignment already exists")
    return obj


@router.delete("/assignments/{aid}", status_code=204)
def delete_assignment(aid: int, _: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    db.delete(get_or_404(db, TeacherAssignment, aid, sid))
    db.commit()
    return Response(status_code=204)
