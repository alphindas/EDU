"""Auth + RBAC + tenancy dependencies."""
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Parent, Role, Student, StudentParent, Teacher, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def _authenticate(creds: HTTPAuthorizationCredentials | None, db: Session) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    uid = decode_token(creds.credentials, "access")
    if uid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    db.info.pop("school_id", None)  # user lookup happens before the tenant is known
    user = db.scalar(select(User).where(User.id == uid))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown or inactive user")
    # From here on every query on this session is auto-filtered to the caller's school.
    if user.school_id is not None:
        db.info["school_id"] = user.school_id
    return user


def current_user_allow_pwchange(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    return _authenticate(creds, db)


def current_user(user: User = Depends(current_user_allow_pwchange)) -> User:
    if user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "password_change_required")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = {r.value for r in roles}

    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return dep


def tenant_id(user: User = Depends(current_user)) -> int:
    if user.school_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This endpoint needs a school-scoped account")
    return user.school_id


# ---- relationship helpers used for row-level permission checks ---------------------
def teacher_of(db: Session, user: User) -> Teacher | None:
    return db.scalar(select(Teacher).where(Teacher.user_id == user.id, Teacher.school_id == user.school_id))


def student_of(db: Session, user: User) -> Student | None:
    return db.scalar(select(Student).where(Student.user_id == user.id, Student.school_id == user.school_id))


def parent_of(db: Session, user: User) -> Parent | None:
    return db.scalar(select(Parent).where(Parent.user_id == user.id, Parent.school_id == user.school_id))


def child_ids(db: Session, user: User) -> set[int]:
    p = parent_of(db, user)
    if not p:
        return set()
    return set(db.scalars(select(StudentParent.student_id).where(StudentParent.parent_id == p.id)))
