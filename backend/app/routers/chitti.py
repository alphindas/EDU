"""CHITTI 2.0 endpoints: one engine, role-specific modes/knowledge/permissions.

student : study_buddy, doubt_solver, english, aptitude, puzzle, career (needs parent consent)
teacher : lesson_plan, study_buddy, doubt_solver
parent  : parent (explains the child's class syllabus; never another child's data)
admin   : lesson_plan, study_buddy
Every call is rate-limited (daily + per-minute), logged for oversight, and grounded in school-approved material first."""
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import chitti, files, gamify, providers, rag
from ..ai import Embedder, get_embedder
from ..ai_usage import charge
from ..config import get_settings
from ..db import get_db
from ..deps import child_ids, current_user, require_roles, tenant_id
from ..llm import pdf_text
from ..models import AiConversation, AiDocument, AiMessage, Role, Student, User
from ..models_v2 import AuditLog, Resource, StudentPrefs, XpEvent
from .structure import get_or_404
from .v2util import burst_limit, class_name_of, consent_ok, log_ai, me_student, require_consent, teacher_sections

router = APIRouter(prefix="/chitti", tags=["chitti"])
ROLE_MODES = {
    "student": ["study_buddy", "doubt_solver", "english", "aptitude", "puzzle", "career"],
    "teacher": ["lesson_plan", "study_buddy", "doubt_solver"],
    "parent": ["parent"],
    "admin": ["lesson_plan", "study_buddy"],
}
LANG_PATTERN = "^(en|te|hi|ml|ta)$"
ALLOWED = {**files.DOC, **files.IMAGE, **files.TEXT}
CHITTI_XP_PER_DAY = 15  # small reward for curiosity, capped so it can't be farmed


def _scope(db: Session, user: User) -> tuple[int | None, str | None, Student | None]:
    """(class_id for library filtering, class name for level, student row)."""
    if user.role == Role.student.value:
        s = me_student(db, user)
        return s.class_id, class_name_of(db, s.class_id), s
    if user.role == Role.parent.value:
        kids = sorted(child_ids(db, user))
        s = db.scalar(select(Student).where(Student.id == kids[0])) if kids else None
        return (s.class_id, class_name_of(db, s.class_id), None) if s else (None, None, None)
    return None, None, None


def _reward_curiosity(db: Session, sid: int, stu: Student | None) -> dict | None:
    if not stu:
        return None
    n = db.scalar(select(func.count()).select_from(XpEvent).where(XpEvent.student_id == stu.id, XpEvent.kind == "chitti",
                                                                  XpEvent.day == date.today())) or 0  # fmt: skip
    return gamify.safe_award(db, sid, stu.id, "chitti", 2, coins=1, world="brain") if n < CHITTI_XP_PER_DAY else None


def _ingest(db: Session, sid: int, user: User, f: UploadFile, embedder: Embedder) -> tuple[AiDocument, bytes, str]:
    rel, ctype, name = files.save_upload(sid, "ai", f, ALLOWED)
    path = Path(get_settings().upload_dir) / rel
    data = path.read_bytes()
    if ctype == "application/pdf":
        text = pdf_text(str(path))
    elif ctype == "text/plain":
        text = data.decode("utf-8", errors="replace")
    else:
        text = chitti.ocr_image(str(path), get_settings().ocr_lang)
    text = text.strip()[: get_settings().ai_max_doc_chars]
    doc = AiDocument(school_id=sid, created_by=user.id, user_id=user.id, name=name, content_type=ctype, file_path=rel, text=text)
    db.add(doc)
    db.flush()
    rag.index_document(db, sid, user.id, doc, embedder)
    db.flush()
    return doc, data, ctype


# ------------------------------------------------------------------ status + consent
@router.get("/status")
def chitti_status(user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    consent = True
    if user.role == Role.student.value:
        consent = consent_ok(db, me_student(db, user))
    return {"provider": providers.provider_name(), "online": providers.configured(), "modes": ROLE_MODES.get(user.role, []),
            "languages": ["en", "te", "hi", "ml", "ta"], "consent": consent,
            "voice": {"stt": ["en-IN", "te-IN", "hi-IN", "ml-IN", "ta-IN"], "tts": ["en-IN", "te-IN", "hi-IN", "ml-IN", "ta-IN"]}}


class ConsentIn(BaseModel):
    student_id: int
    allow: bool


@router.get("/consent")
def get_consent(user: User = Depends(require_roles(Role.parent)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    out = []
    for stid in sorted(child_ids(db, user)):
        s = db.scalar(select(Student).where(Student.id == stid))
        p = db.scalar(select(StudentPrefs).where(StudentPrefs.student_id == stid))
        out.append({"student_id": stid, "name": s.user.full_name if s else "", "allow": bool(p and p.ai_consent),
                    "at": p.ai_consent_at if p else None})  # fmt: skip
    return out


@router.put("/consent")
def set_consent(body: ConsentIn, user: User = Depends(require_roles(Role.parent)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if body.student_id not in child_ids(db, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    p = gamify.prefs(db, sid, body.student_id)
    p.ai_consent, p.ai_consent_by, p.ai_consent_at = body.allow, user.id, datetime.now(timezone.utc)
    db.add(AuditLog(school_id=sid, user_id=user.id, role=user.role, action="PUT", path="/chitti/consent", status_code=200,
                    detail=f"student {body.student_id} ai_consent={body.allow}"))  # fmt: skip
    db.commit()
    return {"student_id": body.student_id, "allow": body.allow}


# ------------------------------------------------------------------ chat in a mode
@router.post("/ask")
def ask(
    text: str = Form(min_length=1, max_length=4000),
    mode: str = Form("study_buddy"),
    lang: str = Form("en", pattern=LANG_PATTERN),
    conversation_id: int | None = Form(None),
    voice: bool = Form(False),
    file: UploadFile | None = File(None),
    user: User = Depends(current_user),
    sid: int = Depends(tenant_id),
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
):
    if mode not in ROLE_MODES.get(user.role, []):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This CHITTI mode is not available for your role")
    stu = require_consent(db, user)
    burst_limit(user.id)
    charge(db, sid, user.id, "chitti", providers.provider_name())
    if conversation_id:
        conv = get_or_404(db, AiConversation, conversation_id, sid)
        if conv.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "AiConversation not found")
    else:
        conv = AiConversation(school_id=sid, created_by=user.id, user_id=user.id, title="")
        db.add(conv)
        db.flush()
    question = text.strip()
    image = None
    doc = None
    if file is not None and file.filename:
        doc, data, ctype = _ingest(db, sid, user, file, embedder)
        if ctype.startswith("image/"):
            image = (data, ctype)
            if doc.text and not providers.configured():
                question = f"{question}\n\n(Text read from the photo: {doc.text[:1500]})"
    class_id, cname, _ = _scope(db, user)
    hits = chitti.school_hits(db, sid, question, class_id, embedder)
    if user.role in (Role.student.value, Role.teacher.value):  # the user's own private notes, never anyone else's
        for p in rag.retrieve(db, sid, user.id, question, embedder):
            from ..search import Hit

            hits.append(Hit({"document_id": p.document_id}, p.document, p.text, p.score))
    if doc and doc.text:
        from ..search import Hit

        hits.insert(0, Hit({"document_id": doc.id}, doc.name, doc.text[:3000], 1.0))
    history = [(m.role, m.content) for m in conv.messages[-8:]]
    reply, provider = chitti.mode_ask(mode, question, lang, cname, history, hits[:5], image, voice=voice)
    sources = [{"name": h.label, "snippet": h.text[:200], **(h.ref if isinstance(h.ref, dict) else {})} for h in hits[:5]]
    um = AiMessage(school_id=sid, created_by=user.id, conversation_id=conv.id, role="user", content=text.strip(),
                   attachment_id=doc.id if doc else None)  # fmt: skip
    am = AiMessage(school_id=sid, created_by=user.id, conversation_id=conv.id, role="assistant", content=reply, sources=sources, provider=provider)
    db.add_all([um, am])
    conv.title = conv.title or question[:60]
    conv.updated_at = datetime.now(timezone.utc)
    log_ai(db, sid, user, f"/chitti/ask:{mode}", question[:300])
    reward = _reward_curiosity(db, sid, stu)
    db.commit()
    return {"conversation_id": conv.id, "reply": reply, "sources": sources, "provider": provider, "mode": mode, "reward": reward,
            "ocr_text": doc.text[:1500] if doc and doc.content_type.startswith("image/") else None}


# ------------------------------------------------------------------ topic search
@router.get("/topic")
def topic(q: str = Query(min_length=2, max_length=120), lang: str = Query("en", pattern=LANG_PATTERN), user: User = Depends(current_user),
          sid: int = Depends(tenant_id), db: Session = Depends(get_db), embedder: Embedder = Depends(get_embedder)):  # fmt: skip
    stu = require_consent(db, user)
    burst_limit(user.id)
    class_id, cname, _ = _scope(db, user)
    out = chitti.topic_search(db, sid, q, lang, cname, class_id, embedder)
    log_ai(db, sid, user, "/chitti/topic", q)
    out["reward"] = _reward_curiosity(db, sid, stu)
    db.commit()
    return out


# ------------------------------------------------------------------ photo doubt
@router.post("/photo-doubt")
def photo_doubt(
    text: str = Form("", max_length=2000), lang: str = Form("en", pattern=LANG_PATTERN), file: UploadFile | None = File(None),
    user: User = Depends(require_roles(Role.student, Role.teacher)), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
):
    stu = require_consent(db, user)
    burst_limit(user.id)
    charge(db, sid, user.id, "photo", providers.provider_name())
    ocr, image = "", None
    if file is not None and file.filename:
        rel, ctype, _ = files.save_upload(sid, "doubts", file, files.IMAGE)
        path = Path(get_settings().upload_dir) / rel
        ocr = chitti.ocr_image(str(path), get_settings().ocr_lang)
        image = (path.read_bytes(), ctype)
    question = (text.strip() or ocr).strip()
    if not question and not (image and providers.configured()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Could not read any text. Type the question or retake a clearer photo.")
    _, cname, _ = _scope(db, user)
    sol = chitti.solve(question, lang, cname, image if providers.configured() else None)
    log_ai(db, sid, user, "/chitti/photo-doubt", question[:300])
    reward = _reward_curiosity(db, sid, stu)
    db.commit()
    return {"ocr_text": ocr, "question": question, **sol, "reward": reward}


@router.get("/practice-similar")
def practice_similar(topic: str = Query("", max_length=120), text: str = Query("", max_length=500), n: int = Query(5, ge=1, le=10),
                     user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):  # fmt: skip
    """Ungraded practice (keys included on purpose: the UI checks instantly and explains). Never touches real quizzes."""
    require_consent(db, user)
    qs = chitti.similar_questions(topic, text, n)
    if not qs and providers.configured():
        found = chitti.topic_search(db, sid, topic or text, "en", None, None, None)
        qs = found["practice"]
    return {"topic": topic, "questions": qs}


# ------------------------------------------------------------------ chapter summary + mind map
class SummaryIn(BaseModel):
    resource_id: int
    chapter: int = Field(0, ge=0)
    lang: str = Field("en", pattern=LANG_PATTERN)


def _extractive(text: str, k: int = 5) -> tuple[list[str], dict]:
    import re
    from collections import Counter

    from ..ai import _tokens

    sents = [s.strip() for s in re.split(r"(?<=[.!?।])\s+", text) if len(s.strip()) > 25]
    freq = Counter(t for s in sents for t in _tokens(s))
    ranked = sorted(sents, key=lambda s: -sum(freq[t] for t in set(_tokens(s))) / (len(_tokens(s)) ** 0.5 or 1))
    top = [s for s in sents if s in ranked[:k]]
    keys = [w for w, _ in freq.most_common(6)]
    mind = {"center": "", "branches": [{"label": w, "items": [s[:90] for s in sents if w in _tokens(s)][:2]} for w in keys]}
    return top, mind


@router.post("/summary")
def summary(body: SummaryIn, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    require_consent(db, user)
    burst_limit(user.id)
    r = get_or_404(db, Resource, body.resource_id, sid)
    chapters = r.chapters or [{"title": r.title, "text": r.text}]
    if body.chapter >= len(chapters):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    ch = chapters[body.chapter]
    text = ch.get("text", "")
    if not text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "This chapter has no readable text")
    bullets, mind = _extractive(text)
    mind["center"] = ch.get("title") or r.title
    provider = "stub"
    if providers.configured():
        try:
            import json

            raw = providers.complete(providers.system_prompt("", body.lang),
                                     [("user", "Summarise this chapter for a student. Return ONLY JSON {\"bullets\": [5 short points], "
                                       "\"mind\": {\"center\": title, \"branches\": [{\"label\": idea, \"items\": [2 short facts]}]}}.\n\n"
                                       + text[:9000])], max_tokens=1000)  # fmt: skip
            d = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            bullets, mind, provider = [str(b) for b in d["bullets"]][:8], d["mind"], providers.provider_name()
        except (providers.LLMError, ValueError, KeyError, TypeError):
            pass
    log_ai(db, sid, user, "/chitti/summary", f"resource {r.id} ch {body.chapter}")
    db.commit()
    return {"title": ch.get("title") or r.title, "bullets": bullets, "mind": mind, "provider": provider}


# ------------------------------------------------------------------ oversight
@router.get("/oversight")
def oversight(limit: int = Query(100, ge=1, le=300), user: User = Depends(require_roles(Role.teacher, Role.admin)),
              sid: int = Depends(tenant_id), db: Session = Depends(get_db)):  # fmt: skip
    """Recent student AI interactions (question text only) for teacher/admin oversight. Teachers: their sections only."""
    q = select(AuditLog, User).join(User, User.id == AuditLog.user_id).where(AuditLog.school_id == sid, AuditLog.action == "AI",
                                                                             User.role == Role.student.value)  # fmt: skip
    if user.role == Role.teacher.value:
        secs = teacher_sections(db, user)
        q = q.join(Student, Student.user_id == User.id).where(Student.section_id.in_(secs or {-1}))
    rows = db.execute(q.order_by(AuditLog.id.desc()).limit(limit)).all()
    return [{"id": a.id, "student": u.full_name, "path": a.path, "question": a.detail, "at": a.created_at} for a, u in rows]


# ------------------------------------------------------------------ chat history (all roles; private to the owner)
@router.get("/conversations")
def conversations(user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    rows = db.scalars(select(AiConversation).where(AiConversation.user_id == user.id).order_by(AiConversation.updated_at.desc()).limit(50))
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in rows]


@router.get("/conversations/{cid}")
def conversation(cid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    c = get_or_404(db, AiConversation, cid, sid)
    if c.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AiConversation not found")
    return {"id": c.id, "title": c.title, "messages": [{"id": m.id, "role": m.role, "content": m.content, "sources": m.sources, "provider": m.provider,
                                                        "created_at": m.created_at} for m in c.messages]}  # fmt: skip


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    c = get_or_404(db, AiConversation, cid, sid)
    if c.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AiConversation not found")
    db.delete(c)
    db.commit()
