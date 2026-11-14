import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_user_allow_pwchange, parent_of, student_of, teacher_of
from ..models import OtpCode, Parent, Role, School, User, utcnow
from ..otp import get_provider
from ..schemas import (
    ChangePasswordIn,
    LoginIn,
    OtpRequestIn,
    OtpVerifyIn,
    ProfilePatch,
    RefreshIn,
    SchoolBrief,
    TokenOut,
    UserOut,
)
from ..security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# ---- tiny in-memory sliding-window rate limiter (swap for Redis in prod) ----------
_hits: dict[str, deque] = defaultdict(deque)


def _window(key: str, window: int) -> deque:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    return q


def check_limit(key: str, limit: int = 10, window: int = 900) -> None:
    """Block if `limit` FAILURES were recorded inside the window."""
    q = _window(key, window)
    if len(q) >= limit:
        wait = int(window - (time.monotonic() - q[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many failed attempts, try again in {max(wait // 60, 1)} min",
            headers={"Retry-After": str(wait)},
        )


def record_failure(key: str) -> None:
    _hits[key].append(time.monotonic())


def clear_failures(key: str) -> None:
    _hits.pop(key, None)


def rate_limit(key: str, limit: int = 10, window: int = 900) -> None:
    """Counts every call (used for OTP *requests*, which are cheap to spam and costly to send)."""
    check_limit(key, limit, window)
    record_failure(key)


def reset_rate_limits() -> None:  # used by tests
    _hits.clear()


BAD = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")


def user_out(db: Session, user: User) -> UserOut:
    out = UserOut.model_validate(user)
    if user.school_id is not None:
        db.info["school_id"] = user.school_id
        school = db.get(School, user.school_id)
        out.school = school and SchoolBrief.model_validate(school)
    if user.role == Role.student.value:
        s = student_of(db, user)
        out.student_id = s.id if s else None
    elif user.role == Role.teacher.value:
        t = teacher_of(db, user)
        out.teacher_id = t.id if t else None
    elif user.role == Role.parent.value:
        p = parent_of(db, user)
        out.parent_id = p.id if p else None
    return out


def issue(db: Session, user: User) -> TokenOut:
    user.last_login_at = utcnow()
    db.commit()
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        must_change_password=user.must_change_password,
        user=user_out(db, user),
    )


def _school(db: Session, code: str | None) -> School | None:
    if not code:
        return None
    return db.scalar(select(School).where(School.code == code.strip()))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    """Admin/teacher/student password login (+ superadmin without school_code). Parents use /auth/otp/*."""
    rl = f"login:{request.client.host if request.client else '?'}:{body.login_id.lower()}"
    check_limit(rl)
    if body.role == Role.parent.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parents sign in with mobile + OTP")
    if body.role not in {r.value for r in Role}:
        raise BAD
    if body.role == Role.superadmin.value:
        school_id = None
    else:
        school = _school(db, body.school_code)
        if not school:
            raise BAD
        school_id = school.id
        db.info["school_id"] = school_id
    stmt = select(User).where(User.role == body.role, User.login_id == body.login_id.strip())
    stmt = stmt.where(User.school_id.is_(None)) if school_id is None else stmt.where(User.school_id == school_id)
    user = db.scalar(stmt)
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        record_failure(rl)
        raise BAD
    clear_failures(rl)
    return issue(db, user)


@router.post("/otp/request")
def otp_request(body: OtpRequestIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"otp:{body.school_code}:{body.mobile}", limit=5, window=600)
    school = _school(db, body.school_code)
    s = get_settings()
    if school:
        db.info["school_id"] = school.id
        parent = db.scalar(select(Parent).where(Parent.mobile == body.mobile.strip()))
        if parent:  # same response either way: do not reveal which mobiles are registered
            prov = get_provider()
            code = prov.generate()
            for old in db.scalars(select(OtpCode).where(OtpCode.mobile == body.mobile.strip(), OtpCode.used.is_(False))):
                old.used = True  # a new request invalidates earlier unused codes
            db.add(
                OtpCode(
                    school_id=school.id,
                    mobile=body.mobile.strip(),
                    code_hash=hash_password(code),
                    expires_at=utcnow() + timedelta(minutes=s.otp_ttl_minutes),
                )
            )
            db.commit()
            prov.send(body.mobile.strip(), code)
    return {"sent": True, "expires_in": s.otp_ttl_minutes * 60}


@router.post("/otp/verify", response_model=TokenOut)
def otp_verify(body: OtpVerifyIn, request: Request, db: Session = Depends(get_db)):
    rl = f"otpv:{body.school_code}:{body.mobile}"
    check_limit(rl, limit=10, window=600)
    school = _school(db, body.school_code)
    if not school:
        raise BAD
    db.info["school_id"] = school.id
    mobile = body.mobile.strip()
    otp = db.scalar(
        select(OtpCode).where(OtpCode.mobile == mobile, OtpCode.used.is_(False)).order_by(OtpCode.id.desc())
    )
    s = get_settings()
    now = datetime.now(timezone.utc)
    if not otp:
        raise BAD
    exp = otp.expires_at if otp.expires_at.tzinfo else otp.expires_at.replace(tzinfo=timezone.utc)
    if exp < now or otp.attempts >= s.otp_max_attempts:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "OTP expired, request a new one")
    otp.attempts += 1
    if not verify_password(body.code, otp.code_hash):
        db.commit()
        record_failure(rl)
        raise BAD
    otp.used = True
    parent = db.scalar(select(Parent).where(Parent.mobile == mobile))
    user = db.get(User, parent.user_id) if parent else None
    if not user or not user.is_active:
        raise BAD
    clear_failures(rl)
    return issue(db, user)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    uid = decode_token(body.refresh_token, "refresh")
    user = db.scalar(select(User).where(User.id == uid)) if uid else None
    if not user or not user.is_active:
        raise BAD
    return issue(db, user)


@router.post("/change-password", response_model=TokenOut)
def change_password(
    body: ChangePasswordIn, user: User = Depends(current_user_allow_pwchange), db: Session = Depends(get_db)
):
    if user.role == Role.parent.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parents use OTP, no password")
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is wrong")
    if body.old_password == body.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must differ")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    return issue(db, user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user_allow_pwchange), db: Session = Depends(get_db)):
    return user_out(db, user)


@router.patch("/me", response_model=UserOut)
def patch_me(body: ProfilePatch, user: User = Depends(current_user_allow_pwchange), db: Session = Depends(get_db)):
    for f in ("phone", "email", "language"):
        v = getattr(body, f)
        if v is not None:
            setattr(user, f, v)
    if user.role == Role.parent.value:
        p = parent_of(db, user)
        if p and body.alert_channels is not None:
            p.alert_channels = body.alert_channels
        if p and body.emergency_contact is not None:
            p.emergency_contact = body.emergency_contact
    db.commit()
    return user_out(db, user)
