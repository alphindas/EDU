from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, tenant_id
from ..models import Notification, User
from ..schemas_p2 import NotificationOut

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False, limit: int = Query(30, ge=1, le=100),
    user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    q = select(Notification).where(Notification.school_id == sid, Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read.is_(False))
    return db.scalars(q.order_by(Notification.id.desc()).limit(limit)).all()


@router.get("/notifications/unread-count")
def unread_count(user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    n = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.school_id == sid, Notification.user_id == user.id, Notification.read.is_(False)
        )
    )
    return {"count": n}


@router.post("/notifications/{nid}/read", status_code=204)
def mark_read(nid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    n = db.scalar(select(Notification).where(Notification.id == nid, Notification.school_id == sid, Notification.user_id == user.id))
    if not n:
        raise HTTPException(404, "Notification not found")
    n.read = True
    db.commit()


@router.post("/notifications/read-all", status_code=204)
def mark_all_read(user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.school_id == sid, Notification.user_id == user.id).values(read=True))
    db.commit()
