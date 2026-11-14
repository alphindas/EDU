"""Communication + collaboration:
- Direct messages: student <-> their own teachers, parent <-> their children's teachers, teacher <-> both (own sections).
- Peer forum (doubts / ideas / showcase) with teacher moderation.
- Counselling / complaint chat: optionally anonymous, readable ONLY by staff flagged as counsellors.
- Project space + digital portfolio."""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .. import files, gamify
from ..db import get_db
from ..deps import child_ids, current_user, require_roles, tenant_id
from ..models import Parent, Role, Student, StudentParent, User
from ..models_v2 import (
    CounsellingMessage, CounsellingThread, DirectMessage, ForumPost, ForumReply, PortfolioItem, Project, ProjectComment, StaffFlag,
)  # fmt: skip
from ..notify import notify
from .structure import get_or_404
from .v2util import is_counsellor, me_student, parents_of_sections, section_teacher_user_ids, target_student, teacher_sections
from .ws import hub

router = APIRouter(tags=["community"])


# ------------------------------------------------------------------ direct messages
def contacts_for(db: Session, user: User) -> set[int]:
    if user.role == Role.student.value:
        return section_teacher_user_ids(db, me_student(db, user).section_id)
    if user.role == Role.parent.value:
        secs = set(db.scalars(select(Student.section_id).where(Student.id.in_(child_ids(db, user) or {-1}))))
        out: set[int] = set()
        for s in secs:
            out |= section_teacher_user_ids(db, s)
        return out
    if user.role == Role.teacher.value:
        secs = teacher_sections(db, user)
        stu = set(db.scalars(select(Student.user_id).where(Student.section_id.in_(secs or {-1}), Student.deleted_at.is_(None))))
        return stu | parents_of_sections(db, secs)
    if user.role == Role.admin.value:
        return set(db.scalars(select(User.id).where(User.school_id == user.school_id, User.role == "teacher")))
    return set()


@router.get("/messages/contacts")
def contacts(user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    ids = contacts_for(db, user)
    unread = dict(db.execute(select(DirectMessage.sender_user_id, func.count()).where(DirectMessage.recipient_user_id == user.id,
                             DirectMessage.read.is_(False)).group_by(DirectMessage.sender_user_id)).all())  # fmt: skip
    rows = db.scalars(select(User).where(User.id.in_(ids or {-1})).order_by(User.role, User.full_name))
    out = []
    for u in rows:
        extra = ""
        if u.role == "parent":
            kids = db.scalars(select(Student).join(StudentParent, StudentParent.student_id == Student.id).join(Parent, Parent.id == StudentParent.parent_id)
                              .where(Parent.user_id == u.id))  # fmt: skip
            extra = ", ".join(k.user.full_name.split(" ")[0] for k in kids)
        out.append({"user_id": u.id, "name": u.full_name, "role": u.role, "unread": unread.get(u.id, 0), "about": extra})
    return sorted(out, key=lambda c: (-c["unread"], c["role"], c["name"]))


@router.get("/messages/thread/{other_id}")
def thread(other_id: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if other_id not in contacts_for(db, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    msgs = list(db.scalars(select(DirectMessage).where(DirectMessage.school_id == sid, or_(
        and_(DirectMessage.sender_user_id == user.id, DirectMessage.recipient_user_id == other_id),
        and_(DirectMessage.sender_user_id == other_id, DirectMessage.recipient_user_id == user.id))).order_by(DirectMessage.id).limit(500)))  # fmt: skip
    for m in msgs:
        if m.recipient_user_id == user.id and not m.read:
            m.read = True
    db.commit()
    return [{"id": m.id, "mine": m.sender_user_id == user.id, "body": m.body, "at": m.created_at, "read": m.read} for m in msgs]


class DmIn(BaseModel):
    to: int
    body: str = Field(min_length=1, max_length=2000)


@router.post("/messages", status_code=201)
def send_dm(body: DmIn, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if body.to not in contacts_for(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only message your own teachers / students / parents")
    m = DirectMessage(school_id=sid, created_by=user.id, sender_user_id=user.id, recipient_user_id=body.to, body=body.body.strip())
    db.add(m)
    notify(db, sid, [body.to], "message", "notif.new_message", {"name": user.full_name}, "messages")
    db.commit()
    hub.send_user(body.to, {"type": "dm", "from": user.id, "name": user.full_name, "body": m.body[:200], "id": m.id})
    return {"id": m.id, "mine": True, "body": m.body, "at": m.created_at, "read": False}


# ------------------------------------------------------------------ forum
def _forum_sections(db: Session, user: User) -> set[int] | None:
    if user.role == Role.student.value:
        return {me_student(db, user).section_id}
    if user.role == Role.teacher.value:
        return teacher_sections(db, user)
    if user.role == Role.admin.value:
        return None
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Forum is for students and staff")


def _can_moderate(db: Session, user: User, p: ForumPost) -> bool:
    return user.role == Role.admin.value or (user.role == Role.teacher.value and (p.section_id is None or p.section_id in teacher_sections(db, user)))


def _post_out(db: Session, user: User, p: ForumPost, replies: list[ForumReply] | None = None) -> dict:
    names = {u.id: (u.full_name, u.role) for u in db.scalars(select(User).where(User.id.in_(
        [p.author_user_id] + [r.author_user_id for r in replies or []])))}  # fmt: skip
    n = db.scalar(select(func.count()).select_from(ForumReply).where(ForumReply.post_id == p.id, ForumReply.hidden.is_(False))) or 0
    d = {"id": p.id, "kind": p.kind, "title": p.title, "body": p.body, "section_id": p.section_id, "subject_id": p.subject_id, "solved": p.solved,
         "hidden": p.hidden, "likes": len(p.likes or []), "liked": user.id in (p.likes or []), "author": names.get(p.author_user_id, ("", ""))[0],
         "author_role": names.get(p.author_user_id, ("", ""))[1], "mine": p.author_user_id == user.id, "replies_count": n,
         "created_at": p.created_at, "can_moderate": _can_moderate(db, user, p)}  # fmt: skip
    if replies is not None:
        mod = d["can_moderate"]
        d["replies"] = [{"id": r.id, "body": r.body, "accepted": r.accepted, "hidden": r.hidden, "author": names.get(r.author_user_id, ("", ""))[0],
                         "author_role": names.get(r.author_user_id, ("", ""))[1], "mine": r.author_user_id == user.id, "created_at": r.created_at}
                        for r in replies if mod or not r.hidden]  # fmt: skip
    return d


@router.get("/forum")
def list_posts(kind: str | None = None, q: str = Query("", max_length=100), user: User = Depends(current_user), sid: int = Depends(tenant_id),
               db: Session = Depends(get_db)):  # fmt: skip
    secs = _forum_sections(db, user)
    stmt = select(ForumPost).where(ForumPost.school_id == sid)
    if secs is not None:
        stmt = stmt.where(or_(ForumPost.section_id.in_(secs or {-1}), ForumPost.section_id.is_(None)))
    if user.role == Role.student.value:
        stmt = stmt.where(or_(ForumPost.hidden.is_(False), ForumPost.author_user_id == user.id))
    if kind:
        stmt = stmt.where(ForumPost.kind == kind)
    if q.strip():
        stmt = stmt.where(or_(ForumPost.title.ilike(f"%{q.strip()}%"), ForumPost.body.ilike(f"%{q.strip()}%")))
    return [_post_out(db, user, p) for p in db.scalars(stmt.order_by(ForumPost.id.desc()).limit(100))]


class PostIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    kind: str = Field("doubt", pattern="^(doubt|idea|showcase)$")
    subject_id: int | None = None
    school_wide: bool = False


@router.post("/forum", status_code=201)
def create_post(body: PostIn, user: User = Depends(require_roles(Role.student, Role.teacher)), sid: int = Depends(tenant_id),
                db: Session = Depends(get_db)):  # fmt: skip
    section = None if body.school_wide else (me_student(db, user).section_id if user.role == "student" else None)
    p = ForumPost(school_id=sid, created_by=user.id, author_user_id=user.id, section_id=section, subject_id=body.subject_id, kind=body.kind,
                  title=body.title.strip(), body=body.body.strip(), likes=[])  # fmt: skip
    db.add(p)
    db.commit()
    return _post_out(db, user, p, [])


def _post(db: Session, user: User, sid: int, pid: int) -> ForumPost:
    p = get_or_404(db, ForumPost, pid, sid)
    secs = _forum_sections(db, user)
    if secs is not None and p.section_id is not None and p.section_id not in secs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ForumPost not found")
    if p.hidden and user.role == "student" and p.author_user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ForumPost not found")
    return p


@router.get("/forum/{pid}")
def get_post(pid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = _post(db, user, sid, pid)
    return _post_out(db, user, p, list(db.scalars(select(ForumReply).where(ForumReply.post_id == p.id).order_by(ForumReply.id))))


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=3000)


@router.post("/forum/{pid}/replies", status_code=201)
def reply(pid: int, body: ReplyIn, user: User = Depends(require_roles(Role.student, Role.teacher, Role.admin)), sid: int = Depends(tenant_id),
          db: Session = Depends(get_db)):  # fmt: skip
    p = _post(db, user, sid, pid)
    db.add(ForumReply(school_id=sid, created_by=user.id, post_id=p.id, author_user_id=user.id, body=body.body.strip()))
    if p.author_user_id != user.id:
        notify(db, sid, [p.author_user_id], "forum", "notif.forum_reply", {"title": p.title[:60], "name": user.full_name}, "forum")
    if user.role == "student":
        gamify.safe_award(db, sid, me_student(db, user).id, "forum", 4, coins=1, world="language")
    db.commit()
    return get_post(pid, user, sid, db)


@router.post("/forum/{pid}/like")
def like(pid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = _post(db, user, sid, pid)
    likes = list(p.likes or [])
    likes.remove(user.id) if user.id in likes else likes.append(user.id)
    p.likes = likes
    db.commit()
    return {"likes": len(likes), "liked": user.id in likes}


class ModIn(BaseModel):
    hidden: bool | None = None
    solved: bool | None = None
    reply_id: int | None = None
    reply_hidden: bool | None = None
    reply_accepted: bool | None = None


@router.patch("/forum/{pid}")
def moderate(pid: int, body: ModIn, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = _post(db, user, sid, pid)
    is_mod = _can_moderate(db, user, p)
    if body.hidden is not None:
        if not is_mod:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only teachers can moderate")
        p.hidden = body.hidden
    if body.solved is not None:
        if not (is_mod or p.author_user_id == user.id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author or a teacher can mark solved")
        p.solved = body.solved
    if body.reply_id is not None:
        r = get_or_404(db, ForumReply, body.reply_id, sid)
        if r.post_id != p.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ForumReply not found")
        if body.reply_hidden is not None:
            if not is_mod:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Only teachers can moderate")
            r.hidden = body.reply_hidden
        if body.reply_accepted is not None:
            if not (is_mod or p.author_user_id == user.id):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author or a teacher can accept")
            r.accepted = body.reply_accepted
            if r.accepted:
                p.solved = True
                helper = db.scalar(select(Student).where(Student.user_id == r.author_user_id))
                if helper:
                    gamify.safe_award(db, sid, helper.id, "forum", 15, coins=5, world="language", meta={"accepted": True})
    db.commit()
    return get_post(pid, user, sid, db)


# ------------------------------------------------------------------ counselling (anonymous allowed)
class CounselIn(BaseModel):
    topic: str = Field("talk", pattern="^(talk|complaint|study_stress|friends|other)$")
    anonymous: bool = True
    body: str = Field(min_length=1, max_length=3000)


def _thread_out(db: Session, t: CounsellingThread, viewer_is_staff: bool) -> dict:
    who = None
    if viewer_is_staff and not t.anonymous:
        who = db.scalar(select(User.full_name).where(User.id == t.student_user_id))
    msgs = list(db.scalars(select(CounsellingMessage).where(CounsellingMessage.thread_id == t.id).order_by(CounsellingMessage.id)))
    return {"id": t.id, "topic": t.topic, "anonymous": t.anonymous, "status": t.status, "student": who if viewer_is_staff else None,
            "created_at": t.created_at, "messages": [{"id": m.id, "from_staff": m.from_staff, "body": m.body, "at": m.created_at} for m in msgs]}


@router.post("/counselling", status_code=201)
def open_thread(body: CounselIn, user: User = Depends(require_roles(Role.student)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    t = CounsellingThread(school_id=sid, created_by=user.id, student_user_id=user.id, topic=body.topic, anonymous=body.anonymous)
    db.add(t)
    db.flush()
    db.add(CounsellingMessage(school_id=sid, thread_id=t.id, from_staff=False, body=body.body.strip()))
    counsellors = set(db.scalars(select(StaffFlag.user_id).where(StaffFlag.school_id == sid, StaffFlag.counsellor.is_(True))))
    notify(db, sid, counsellors, "counselling", "notif.counselling_new", {}, "counselling")
    db.commit()
    return _thread_out(db, t, False)


@router.get("/counselling")
def my_threads(user: User = Depends(require_roles(Role.student)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return [_thread_out(db, t, False) for t in db.scalars(select(CounsellingThread).where(CounsellingThread.student_user_id == user.id)
                                                          .order_by(CounsellingThread.id.desc()))]  # fmt: skip


@router.get("/counselling/inbox")
def inbox(user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if not is_counsellor(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only school counsellors can open this inbox")
    return [_thread_out(db, t, True) for t in db.scalars(select(CounsellingThread).where(CounsellingThread.school_id == sid)
                                                         .order_by(CounsellingThread.status.desc(), CounsellingThread.id.desc()).limit(200))]  # fmt: skip


class CMsgIn(BaseModel):
    body: str = Field(min_length=1, max_length=3000)
    close: bool = False


@router.post("/counselling/{tid}/messages")
def counsel_reply(tid: int, body: CMsgIn, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    t = get_or_404(db, CounsellingThread, tid, sid)
    staff = is_counsellor(db, user)
    if not staff and t.student_user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CounsellingThread not found")
    db.add(CounsellingMessage(school_id=sid, thread_id=t.id, from_staff=staff, staff_user_id=user.id if staff else None, body=body.body.strip()))
    if staff:
        notify(db, sid, [t.student_user_id], "counselling", "notif.counselling_reply", {}, "counselling")
        if body.close:
            t.status = "closed"
    else:
        t.status = "open"
        counsellors = set(db.scalars(select(StaffFlag.user_id).where(StaffFlag.school_id == sid, StaffFlag.counsellor.is_(True))))
        notify(db, sid, counsellors, "counselling", "notif.counselling_new", {}, "counselling")
    db.commit()
    return _thread_out(db, t, staff)


class FlagIn(BaseModel):
    counsellor: bool


@router.get("/staff-flags")
def list_flags(user: User = Depends(require_roles(Role.admin)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    flags = {f.user_id: f.counsellor for f in db.scalars(select(StaffFlag).where(StaffFlag.school_id == sid))}
    staff = db.scalars(select(User).where(User.school_id == sid, User.role.in_(["teacher", "admin"])).order_by(User.full_name))
    return [{"user_id": u.id, "name": u.full_name, "role": u.role, "counsellor": flags.get(u.id, False)} for u in staff]


@router.put("/staff-flags/{uid}")
def set_flag(uid: int, body: FlagIn, user: User = Depends(require_roles(Role.admin)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.id == uid, User.school_id == sid, User.role.in_(["teacher", "admin"])))
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
    f = db.scalar(select(StaffFlag).where(StaffFlag.user_id == uid))
    if not f:
        f = StaffFlag(school_id=sid, user_id=uid)
        db.add(f)
    f.counsellor = body.counsellor
    db.commit()
    return {"user_id": uid, "counsellor": f.counsellor}


# ------------------------------------------------------------------ projects
class ProjectIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field("", max_length=3000)
    category: str = Field("science", pattern="^(science|coding|art|social|robotics|other)$")
    max_members: int = Field(4, ge=1, le=10)
    emoji: str = Field("🚀", max_length=8)


def _proj_out(db: Session, user: User, p: Project, with_comments: bool = False) -> dict:
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(list(p.members or []) + [p.owner_user_id])))}
    d = {"id": p.id, "title": p.title, "summary": p.summary, "category": p.category, "status": p.status, "emoji": p.emoji,
         "max_members": p.max_members, "members": [{"user_id": m, "name": names.get(m, "")} for m in p.members or []],
         "owner": names.get(p.owner_user_id, ""), "mine": p.owner_user_id == user.id, "joined": user.id in (p.members or []),
         "created_at": p.created_at}  # fmt: skip
    if with_comments:
        cs = list(db.scalars(select(ProjectComment).where(ProjectComment.project_id == p.id).order_by(ProjectComment.id)))
        cn = {u.id: (u.full_name, u.role) for u in db.scalars(select(User).where(User.id.in_([c.author_user_id for c in cs] or [-1])))}
        d["comments"] = [{"id": c.id, "body": c.body, "author": cn.get(c.author_user_id, ("", ""))[0], "role": cn.get(c.author_user_id, ("", ""))[1],
                          "at": c.created_at} for c in cs]  # fmt: skip
    return d


@router.get("/projects")
def list_projects(user: User = Depends(require_roles(Role.student, Role.teacher, Role.admin)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return [_proj_out(db, user, p) for p in db.scalars(select(Project).where(Project.school_id == sid).order_by(Project.id.desc()).limit(200))]


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, user: User = Depends(require_roles(Role.student)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = Project(school_id=sid, created_by=user.id, owner_user_id=user.id, members=[user.id], **body.model_dump())
    db.add(p)
    gamify.safe_award(db, sid, me_student(db, user).id, "project", 20, coins=8, world="innovation")
    db.commit()
    return _proj_out(db, user, p, True)


@router.get("/projects/{pid}")
def get_project(pid: int, user: User = Depends(require_roles(Role.student, Role.teacher, Role.admin)), sid: int = Depends(tenant_id),
                db: Session = Depends(get_db)):  # fmt: skip
    return _proj_out(db, user, get_or_404(db, Project, pid, sid), True)


@router.post("/projects/{pid}/join")
def join_project(pid: int, user: User = Depends(require_roles(Role.student)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = get_or_404(db, Project, pid, sid)
    members = list(p.members or [])
    if user.id in members:
        members.remove(user.id) if p.owner_user_id != user.id else None
    else:
        if p.status != "open" or len(members) >= p.max_members:
            raise HTTPException(status.HTTP_409_CONFLICT, "This project is full or not accepting members")
        members.append(user.id)
        notify(db, sid, [p.owner_user_id], "project", "notif.project_join", {"name": user.full_name, "title": p.title[:60]}, "projects")
        gamify.safe_award(db, sid, me_student(db, user).id, "project", 10, coins=3, world="innovation")
    p.members = members
    db.commit()
    return _proj_out(db, user, p, True)


class ProjPatch(BaseModel):
    status: str | None = Field(None, pattern="^(open|building|done)$")
    summary: str | None = Field(None, max_length=3000)


@router.patch("/projects/{pid}")
def patch_project(pid: int, body: ProjPatch, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    p = get_or_404(db, Project, pid, sid)
    if p.owner_user_id != user.id and user.role not in ("teacher", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner or staff can edit")
    if body.status:
        p.status = body.status
    if body.summary is not None:
        p.summary = body.summary
    db.commit()
    return _proj_out(db, user, p, True)


@router.post("/projects/{pid}/comments", status_code=201)
def comment_project(pid: int, body: ReplyIn, user: User = Depends(require_roles(Role.student, Role.teacher, Role.admin)), sid: int = Depends(tenant_id),
                    db: Session = Depends(get_db)):  # fmt: skip
    p = get_or_404(db, Project, pid, sid)
    db.add(ProjectComment(school_id=sid, created_by=user.id, project_id=p.id, author_user_id=user.id, body=body.body.strip()))
    if p.owner_user_id != user.id:
        notify(db, sid, [p.owner_user_id], "project", "notif.project_comment", {"name": user.full_name, "title": p.title[:60]}, "projects")
    db.commit()
    return _proj_out(db, user, p, True)


# ------------------------------------------------------------------ portfolio
PORT_FILES = {**files.IMAGE, **files.DOC}


def _port_out(i: PortfolioItem) -> dict:
    return {"id": i.id, "kind": i.kind, "title": i.title, "details": i.details, "achieved_on": i.achieved_on, "has_file": bool(i.file_path),
            "content_type": i.content_type, "created_at": i.created_at}


@router.get("/portfolio")
def portfolio(student_id: int | None = None, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = target_student(db, user, sid, student_id)
    return [_port_out(i) for i in db.scalars(select(PortfolioItem).where(PortfolioItem.student_id == stu.id).order_by(PortfolioItem.id.desc()))]


@router.post("/portfolio", status_code=201)
def add_portfolio(
    kind: str = Form(pattern="^(certificate|sports|art|project|award|other)$"), title: str = Form(min_length=1, max_length=200),
    details: str = Form("", max_length=2000), achieved_on: date | None = Form(None), file: UploadFile | None = File(None),
    user: User = Depends(require_roles(Role.student)), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    stu = me_student(db, user)
    i = PortfolioItem(school_id=sid, created_by=user.id, student_id=stu.id, kind=kind, title=title.strip(), details=details.strip(), achieved_on=achieved_on)
    if file is not None and file.filename:
        i.file_path, i.content_type, i.original_name = files.save_upload(sid, "portfolio", file, PORT_FILES)
    db.add(i)
    gamify.safe_award(db, sid, stu.id, "portfolio", 6, coins=2, world="innovation")
    db.commit()
    return _port_out(i)


@router.get("/portfolio/{iid}/file")
def portfolio_file(iid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    i = get_or_404(db, PortfolioItem, iid, sid)
    target_student(db, user, sid, i.student_id)  # row-level check (404 if not allowed)
    if not i.file_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No file")
    return files.serve(sid, i.file_path, i.content_type, i.original_name)


@router.delete("/portfolio/{iid}", status_code=204)
def delete_portfolio(iid: int, user: User = Depends(require_roles(Role.student)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    i = get_or_404(db, PortfolioItem, iid, sid)
    if i.student_id != me_student(db, user).id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PortfolioItem not found")
    path = i.file_path
    db.delete(i)
    db.commit()
    files.remove(path)
