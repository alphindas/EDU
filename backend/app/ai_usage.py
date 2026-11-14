"""Per-user daily AI call limit + audit log (blueprint §14 safety rules: log every AI call, set daily limits)."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AiCall


def charge(db: Session, school_id: int, user_id: int, kind: str, provider: str) -> None:
    """Record one provider call, or raise 429 when the user is over today's limit. Caller commits."""
    day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    used = db.scalar(select(func.count()).select_from(AiCall).where(AiCall.user_id == user_id, AiCall.created_at >= day)) or 0
    if used >= get_settings().ai_daily_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Daily AI limit reached. Try again tomorrow.")
    db.add(AiCall(school_id=school_id, created_by=user_id, user_id=user_id, kind=kind, provider=provider))
