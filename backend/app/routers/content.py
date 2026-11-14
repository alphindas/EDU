"""Content library (syllabus, notes, textbooks, previous-year papers, e-books, video/audio links) + announcements.

Teachers/admins upload; students see their class (and school-wide) items; parents see their children's classes.
Text is extracted per chapter/page so CHITTI can cite "Title · Chapter/Page" and students can search inside books."""
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import files, gamify
from ..config import get_settings
from ..db import get_db
from ..deps import child_ids, current_user, require_roles, tenant_id
from ..models import Role, Section, Student, User
from ..models_v2 import Announcement, Resource, ResourceProgress
from ..notify import notify
from .structure import get_or_404
from .v2util import me_student, parents_of_sections, teacher_sections

router = APIRouter(tags=["library"])
staff = require_roles(Role.teacher, Role.admin)
KINDS = ("syllabus", "notes", "textbook", "paper", "ebook", "video", "audio")
UPLOAD = {**files.DOC, **files.TEXT, **files.IMAGE, **files.AUDIO}
_HEAD = re.compile(r"^\s*((?:chapter|unit|lesson|अध्याय|పాఠం|അധ്യായം|பாடம்)\s*[\dIVX]+[^\n]{0,80})$", re.I | re.M)


def split_chapters(text: str, pages: list[str] | None = None) -> list[dict]:
    """Heading-based chapters ("Chapter 3 …"); otherwise one entry per PDF page; otherwise a single chapter."""
    marks = list(_HEAD.finditer(text))
    if len(marks) >= 2:
        out = []
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            out.append({"title": m[1].strip()[:120], "text": text[m.end():end].strip()})
        return [c for c in out if c["text"]]
    if pages and len(pages) > 1:
        return [{"title": f"Page {i + 1}", "text": p.strip()} for i, p in enumerate(pages) if p.strip()]
    return [{"title": "Full text", "text": text.strip()}] if text.strip() else []


def _pdf_pages(path: str, max_pages: int = 300) -> list[str]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        return [(p.extract_text() or "") for p in PdfReader(path).pages[:max_pages]]
    except (PyPdfError, ValueError, OSError, KeyError):
        return []


def _visible_class_ids(db: Session, user: User) -> set[int] | None:
    """None = everything (staff)."""
    if user.role == Role.student.value:
        return {me_student(db, user).class_id}
    if user.role == Role.parent.value:
        kids = child_ids(db, user)
        return set(db.scalars(select(Student.class_id).where(Student.id.in_(kids or {-1}))))
    return None


def _out(r: Resource, prog: ResourceProgress | None = None, detail: bool = False) -> dict:
    d = {"id": r.id, "kind": r.kind, "title": r.title, "description": r.description, "class_id": r.class_id, "subject_id": r.subject_id,
         "year": r.year, "institution": r.institution, "has_file": bool(r.file_path), "content_type": r.content_type, "url": r.url,
         "chapter_count": len(r.chapters or []), "approved": r.approved, "created_at": r.created_at,
         "completed": prog.completed_chapters if prog else [], "bookmarks": prog.bookmarks if prog else []}  # fmt: skip
    if detail:
        d["chapters"] = [{"title": c.get("title", ""), "text": c.get("text", "")} for c in (r.chapters or [])]
    return d


@router.get("/library")
def list_resources(kind: str | None = None, subject_id: int | None = None, class_id: int | None = None, year: int | None = None,
                   q: str = Query("", max_length=100), limit: int = Query(100, ge=1, le=300), user: User = Depends(current_user),
                   sid: int = Depends(tenant_id), db: Session = Depends(get_db)):  # fmt: skip
    stmt = select(Resource).where(Resource.school_id == sid)
    vis = _visible_class_ids(db, user)
    if vis is not None:
        stmt = stmt.where(or_(Resource.class_id.in_(vis or {-1}), Resource.class_id.is_(None)), Resource.approved.is_(True))
    if kind:
        stmt = stmt.where(Resource.kind == kind)
    if subject_id:
        stmt = stmt.where(Resource.subject_id == subject_id)
    if class_id:
        stmt = stmt.where(Resource.class_id == class_id)
    if year:
        stmt = stmt.where(Resource.year == year)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Resource.title.ilike(like), Resource.description.ilike(like), Resource.text.ilike(like)))
    rows = list(db.scalars(stmt.order_by(Resource.id.desc()).limit(limit)))
    progs = {p.resource_id: p for p in db.scalars(select(ResourceProgress).where(ResourceProgress.user_id == user.id))}
    return [_out(r, progs.get(r.id)) for r in rows]


def _load(db: Session, user: User, sid: int, rid: int) -> Resource:
    r = get_or_404(db, Resource, rid, sid)
    vis = _visible_class_ids(db, user)
    if vis is not None and ((r.class_id is not None and r.class_id not in vis) or not r.approved):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    return r


@router.post("/library", status_code=201)
def create_resource(
    kind: str = Form(...), title: str = Form(min_length=1, max_length=200), description: str = Form("", max_length=2000),
    class_id: int | None = Form(None), subject_id: int | None = Form(None), year: int | None = Form(None),
    institution: str = Form("", max_length=120), url: str = Form("", max_length=500), text: str = Form("", max_length=400_000),
    file: UploadFile | None = File(None), user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    if kind not in KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"kind must be one of {', '.join(KINDS)}")
    if url and not url.startswith(("https://", "http://")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "url must start with http(s)://")
    r = Resource(school_id=sid, created_by=user.id, kind=kind, title=title.strip(), description=description.strip(), class_id=class_id,
                 subject_id=subject_id, year=year, institution=institution.strip(), url=url.strip(), text=text.strip())  # fmt: skip
    pages = None
    if file is not None and file.filename:
        r.file_path, r.content_type, r.original_name = files.save_upload(sid, "library", file, UPLOAD)
        path = Path(get_settings().upload_dir) / r.file_path
        if r.content_type == "application/pdf":
            pages = _pdf_pages(str(path))
            r.text = (r.text + "\n" + "\n".join(pages)).strip()
        elif r.content_type == "text/plain":
            r.text = (r.text + "\n" + path.read_text("utf-8", errors="replace")).strip()
        elif r.content_type.startswith("image/"):
            from ..chitti import ocr_image

            r.text = (r.text + "\n" + ocr_image(str(path), get_settings().ocr_lang)).strip()
    r.text = r.text[: get_settings().ai_max_doc_chars * 2]
    r.chapters = split_chapters(r.text, pages)
    db.add(r)
    db.commit()
    return _out(r, detail=True)


@router.get("/library/{rid}")
def get_resource(rid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r = _load(db, user, sid, rid)
    prog = db.scalar(select(ResourceProgress).where(ResourceProgress.resource_id == r.id, ResourceProgress.user_id == user.id))
    return _out(r, prog, detail=True)


@router.get("/library/{rid}/file")
def resource_file(rid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r = _load(db, user, sid, rid)
    if not r.file_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No file")
    return files.serve(sid, r.file_path, r.content_type, r.original_name)


@router.get("/library/{rid}/search")
def search_in(rid: int, q: str = Query(min_length=2, max_length=80), user: User = Depends(current_user), sid: int = Depends(tenant_id),
              db: Session = Depends(get_db)):  # fmt: skip
    r = _load(db, user, sid, rid)
    hits = []
    needle = q.casefold()
    for i, ch in enumerate(r.chapters or []):
        t = ch.get("text", "")
        for m in re.finditer(re.escape(needle), t.casefold()):
            a, b = max(0, m.start() - 60), min(len(t), m.end() + 60)
            hits.append({"chapter": i, "title": ch.get("title", ""), "snippet": t[a:b]})
            if len(hits) >= 50:
                return hits
    return hits


class ProgressIn(BaseModel):
    complete_chapter: int | None = Field(None, ge=0)
    uncomplete_chapter: int | None = Field(None, ge=0)
    bookmark: dict | None = None  # {chapter, note}
    remove_bookmark: int | None = None  # index


@router.patch("/library/{rid}/progress")
def progress(rid: int, body: ProgressIn, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r = _load(db, user, sid, rid)
    p = db.scalar(select(ResourceProgress).where(ResourceProgress.resource_id == r.id, ResourceProgress.user_id == user.id))
    if not p:
        p = ResourceProgress(school_id=sid, resource_id=r.id, user_id=user.id, completed_chapters=[], bookmarks=[])
        db.add(p)
    done = list(p.completed_chapters or [])
    reward = None
    if body.complete_chapter is not None and body.complete_chapter not in done:
        done.append(body.complete_chapter)
        if user.role == Role.student.value:
            stu = me_student(db, user)
            reward = gamify.safe_award(db, sid, stu.id, "reading", 8, coins=2, world=gamify.subject_world(db, r.subject_id) or "language")
    if body.uncomplete_chapter is not None and body.uncomplete_chapter in done:
        done.remove(body.uncomplete_chapter)
    p.completed_chapters = sorted(done)
    marks = list(p.bookmarks or [])
    if body.bookmark and isinstance(body.bookmark.get("chapter"), int):
        marks.append({"chapter": body.bookmark["chapter"], "note": str(body.bookmark.get("note", ""))[:200]})
    if body.remove_bookmark is not None and 0 <= body.remove_bookmark < len(marks):
        marks.pop(body.remove_bookmark)
    p.bookmarks = marks[-100:]
    db.commit()
    return {"completed": p.completed_chapters, "bookmarks": p.bookmarks, "reward": reward}


@router.delete("/library/{rid}", status_code=204)
def delete_resource(rid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r = get_or_404(db, Resource, rid, sid)
    if user.role != Role.admin.value and r.created_by != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the uploader or an admin can delete this")
    for p in db.scalars(select(ResourceProgress).where(ResourceProgress.resource_id == r.id)):
        db.delete(p)
    path = r.file_path
    db.delete(r)
    db.commit()
    files.remove(path)


# ------------------------------------------------------------------ announcements
AUDIENCES = ("all", "students", "teachers", "parents", "staff")


class AnnIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    audience: str = Field("all", pattern="^(all|students|teachers|parents|staff)$")
    section_id: int | None = None
    pinned: bool = False
    emoji: str = Field("📢", max_length=8)


def _ann_visible(db: Session, user: User, a: Announcement) -> bool:
    role = user.role
    if role == Role.admin.value or a.author_user_id == user.id:
        return True
    aud_ok = a.audience == "all" or (a.audience == "students" and role == "student") or (a.audience == "teachers" and role == "teacher") \
        or (a.audience == "parents" and role == "parent") or (a.audience == "staff" and role in ("teacher", "admin"))
    if not aud_ok:
        return False
    if a.section_id is None:
        return True
    if role == "student":
        return me_student(db, user).section_id == a.section_id
    if role == "parent":
        kids = child_ids(db, user)
        return a.section_id in set(db.scalars(select(Student.section_id).where(Student.id.in_(kids or {-1}))))
    if role == "teacher":
        return a.section_id in teacher_sections(db, user)
    return False


def _ann_out(db: Session, a: Announcement) -> dict:
    author = db.scalar(select(User.full_name).where(User.id == a.author_user_id)) or ""
    return {"id": a.id, "title": a.title, "body": a.body, "audience": a.audience, "section_id": a.section_id, "pinned": a.pinned,
            "emoji": a.emoji, "author": author, "created_at": a.created_at}


@router.get("/announcements")
def list_announcements(limit: int = Query(50, ge=1, le=200), user: User = Depends(current_user), sid: int = Depends(tenant_id),
                       db: Session = Depends(get_db)):  # fmt: skip
    rows = db.scalars(select(Announcement).where(Announcement.school_id == sid).order_by(Announcement.pinned.desc(), Announcement.id.desc()).limit(400))
    return [_ann_out(db, a) for a in rows if _ann_visible(db, user, a)][:limit]


@router.post("/announcements", status_code=201)
def create_announcement(body: AnnIn, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if user.role == Role.teacher.value:
        secs = teacher_sections(db, user)
        if body.section_id is None or body.section_id not in secs:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Teachers post announcements to one of their own sections")
        if body.audience not in ("all", "students", "parents"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Teachers post to students and/or parents")
    if body.section_id is not None:
        get_or_404(db, Section, body.section_id, sid)
    a = Announcement(school_id=sid, created_by=user.id, author_user_id=user.id, **body.model_dump())
    db.add(a)
    db.flush()
    # in-app notification to the audience
    q = select(User.id).where(User.school_id == sid, User.is_active.is_(True), User.id != user.id)
    roles = {"all": ["student", "teacher", "parent"], "students": ["student"], "teachers": ["teacher"], "parents": ["parent"],
             "staff": ["teacher"]}[body.audience]  # fmt: skip
    targets = set(db.scalars(q.where(User.role.in_(roles))))
    if body.section_id is not None:
        in_sec = set(db.scalars(select(Student.user_id).where(Student.section_id == body.section_id)))
        in_sec |= parents_of_sections(db, {body.section_id})
        in_sec |= set(db.scalars(select(User.id).where(User.role == "teacher")))
        targets &= in_sec
    notify(db, sid, targets, "announcement", "notif.announcement", {"title": a.title}, "announcements")
    db.commit()
    return _ann_out(db, a)


@router.delete("/announcements/{aid}", status_code=204)
def delete_announcement(aid: int, user: User = Depends(staff), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    a = get_or_404(db, Announcement, aid, sid)
    if user.role != Role.admin.value and a.author_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author or an admin can delete this")
    db.delete(a)
    db.commit()
