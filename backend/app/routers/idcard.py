"""Student ID card + QR. The QR carries a signed token (not just the admission number), so a printed QR can't be
forged by guessing admission numbers: EDN1.<school_code>.<admission_no>.<hmac>."""
import base64
import hashlib
import hmac
import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_user, require_roles, tenant_id
from ..models import AcademicYear, Role, School, SchoolClass, Section, Student, User
from ..schemas_p2 import IdCardOut, IdVerifyIn, IdVerifyOut
from .people import _authorise_student
from .structure import get_or_404

router = APIRouter(tags=["id-card"])
staff = require_roles(Role.admin, Role.teacher)


def _sig(school_id: int, admission_no: str) -> str:
    mac = hmac.new(get_settings().secret_key.encode(), f"{school_id}:{admission_no}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac)[:16].decode()


def make_payload(school: School, admission_no: str) -> str:
    return f"EDN1.{school.code}.{admission_no}.{_sig(school.id, admission_no)}"


def _card(db: Session, sid: int, s: Student) -> IdCardOut:
    school = db.get(School, sid)
    cls = db.scalar(select(SchoolClass).where(SchoolClass.id == s.class_id))
    sec = db.scalar(select(Section).where(Section.id == s.section_id))
    year = db.scalar(select(AcademicYear).where(AcademicYear.school_id == sid, AcademicYear.is_current.is_(True)))
    return IdCardOut(
        student_id=s.id, admission_no=s.admission_no, full_name=s.user.full_name, class_name=cls.name if cls else "",
        section_name=sec.name if sec else "", roll_no=s.roll_no, dob=s.dob, gender=s.gender, photo_url=s.photo_url,
        parent_mobile=s.parent_mobile, school_name=school.name, school_code=school.code, school_address=school.address,
        logo_url=school.logo_url, academic_year=year.label if year else "", qr_payload=make_payload(school, s.admission_no),
    )  # fmt: skip


def _student(db: Session, user: User, sid: int, student_id: int) -> Student:
    s = get_or_404(db, Student, student_id, sid)
    if s.deleted_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    _authorise_student(db, user, s)
    return s


@router.get("/students/{student_id}/id-card", response_model=IdCardOut)
def id_card(student_id: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return _card(db, sid, _student(db, user, sid, student_id))


@router.get("/students/{student_id}/id-card/qr.png")
def id_card_qr(student_id: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    s = _student(db, user, sid, student_id)
    img = qrcode.make(make_payload(db.get(School, sid), s.admission_no), box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "private, no-store"})


@router.post("/id/verify", response_model=IdVerifyOut)
def verify(body: IdVerifyIn, _: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Gate/desk check: scan the QR (or paste its text). Cards from other schools or with a bad signature are invalid."""
    parts = body.payload.strip().split(".")
    if len(parts) != 4 or parts[0] != "EDN1":
        return IdVerifyOut(valid=False, reason="malformed")
    _, code, adm, sig = parts
    school = db.get(School, sid)
    if code != school.code:
        return IdVerifyOut(valid=False, reason="wrong_school")
    if not hmac.compare_digest(sig, _sig(sid, adm)):
        return IdVerifyOut(valid=False, reason="bad_signature")
    s = db.scalar(select(Student).where(Student.school_id == sid, Student.admission_no == adm, Student.deleted_at.is_(None)))
    if not s:
        return IdVerifyOut(valid=False, reason="not_found")
    return IdVerifyOut(valid=True, student=_card(db, sid, s))
