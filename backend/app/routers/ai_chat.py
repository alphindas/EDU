"""AI Chat: private conversations with history, text + file upload, retrieval over the user's own uploaded notes.
Open to students and teachers (blueprint §11). Every conversation/document is owned by one user; other users in the same
school get 404, other schools never see it (tenant filter)."""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import files, rag
from ..ai import Attachment, Embedder, Tutor, get_embedder, get_tutor
from ..ai_usage import charge
from ..config import get_settings
from ..db import get_db
from ..deps import require_roles, tenant_id
from ..llm import pdf_text
from ..models import AiChunk, AiConversation, AiDocument, AiMessage, Role, User
from ..schemas_p4 import AiMessageOut, ChatTurnOut, ConversationDetail, ConversationIn, ConversationOut, DocumentOut
from .structure import get_or_404

router = APIRouter(prefix="/ai", tags=["ai-chat"])
ai_user = require_roles(Role.student, Role.teacher)
ALLOWED = {**files.DOC, **files.IMAGE, **files.TEXT}
HISTORY_TURNS = 10


def _conv(db: Session, sid: int, user: User, cid: int) -> AiConversation:
    c = get_or_404(db, AiConversation, cid, sid)
    if c.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AiConversation not found")
    return c


def _doc(db: Session, sid: int, user: User, did: int) -> AiDocument:
    d = get_or_404(db, AiDocument, did, sid)
    if d.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AiDocument not found")
    return d


def _doc_out(d: AiDocument) -> DocumentOut:
    return DocumentOut(id=d.id, name=d.name, content_type=d.content_type, chunk_count=d.chunk_count, readable=bool(d.text), created_at=d.created_at)


def _ingest(db: Session, sid: int, user: User, f: UploadFile, embedder: Embedder) -> AiDocument:
    """Store the upload (sniffed type, private path), extract text, chunk + embed it for retrieval."""
    rel, ctype, name = files.save_upload(sid, "ai", f, ALLOWED)
    path = Path(get_settings().upload_dir) / rel
    if ctype == "application/pdf":
        text = pdf_text(str(path))
    elif ctype == "text/plain":
        text = path.read_text("utf-8", errors="replace")
    else:
        text = ""  # image: no OCR connected yet
    text = text.strip()[: get_settings().ai_max_doc_chars]
    doc = AiDocument(school_id=sid, created_by=user.id, user_id=user.id, name=name, content_type=ctype, file_path=rel, text=text)
    db.add(doc)
    db.flush()
    rag.index_document(db, sid, user.id, doc, embedder)
    db.flush()  # sessions run with autoflush off: make the new chunks visible to retrieval in this request
    return doc


# ---------------------------------------------------------------- conversations
@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(ai_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return list(db.scalars(select(AiConversation).where(AiConversation.user_id == user.id).order_by(AiConversation.updated_at.desc(), AiConversation.id.desc())))


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(body: ConversationIn, user: User = Depends(ai_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    c = AiConversation(school_id=sid, created_by=user.id, user_id=user.id, title=body.title.strip())
    db.add(c)
    db.commit()
    return c


@router.get("/conversations/{cid}", response_model=ConversationDetail)
def get_conversation(cid: int, user: User = Depends(ai_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return _conv(db, sid, user, cid)


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: int, user: User = Depends(ai_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    db.delete(_conv(db, sid, user, cid))
    db.commit()


@router.post("/conversations/{cid}/messages", response_model=ChatTurnOut, status_code=201)
def send_message(
    cid: int,
    text: str = Form(min_length=1, max_length=2000),
    lang: str = Form("en", pattern="^(en|te|hi|ml|ta)$"),
    file: UploadFile | None = File(None),
    user: User = Depends(ai_user),
    sid: int = Depends(tenant_id),
    db: Session = Depends(get_db),
    tutor: Tutor = Depends(get_tutor),
    embedder: Embedder = Depends(get_embedder),
):
    from .v2util import require_consent  # EduNest 2.0: students need parent consent for AI

    require_consent(db, user)
    conv = _conv(db, sid, user, cid)
    question = text.strip()
    if not question:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Message is empty")
    charge(db, sid, user.id, "chat", tutor.name)  # 429 before any file is stored
    doc = _ingest(db, sid, user, file, embedder) if file is not None and file.filename else None
    attachments = [Attachment(doc.name, doc.content_type, doc.text)] if doc else []
    passages = rag.retrieve(db, sid, user.id, question, embedder)
    history = [(m.role, m.content) for m in conv.messages[-HISTORY_TURNS:]]
    reply = tutor.chat(question, history, passages, attachments, lang)  # only the question, history and passages cross; no identity
    um = AiMessage(school_id=sid, created_by=user.id, conversation_id=conv.id, role="user", content=question, attachment_id=doc.id if doc else None)
    sources = [{"document_id": p.document_id, "name": p.document, "snippet": p.text[:200]} for p in reply.used_passages]
    am = AiMessage(school_id=sid, created_by=user.id, conversation_id=conv.id, role="assistant", content=reply.text, sources=sources, provider=tutor.name)
    db.add_all([um, am])
    if not conv.title:
        conv.title = question[:60]
    conv.updated_at = datetime.now(timezone.utc)  # bump so the thread sorts first
    db.commit()
    return ChatTurnOut(user_message=AiMessageOut.model_validate(um), assistant_message=AiMessageOut.model_validate(am),
                       document=_doc_out(doc) if doc else None)  # fmt: skip


# ---------------------------------------------------------------- documents (the user's notes)
@router.get("/documents", response_model=list[DocumentOut])
def list_documents(user: User = Depends(ai_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return [_doc_out(d) for d in db.scalars(select(AiDocument).where(AiDocument.user_id == user.id).order_by(AiDocument.id.desc()))]


@router.post("/documents", response_model=DocumentOut, status_code=201)
def upload_document(file: UploadFile = File(...), user: User = Depends(ai_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
                    embedder: Embedder = Depends(get_embedder)):  # fmt: skip
    doc = _ingest(db, sid, user, file, embedder)
    db.commit()
    return _doc_out(doc)


@router.get("/documents/{did}/file")
def document_file(did: int, user: User = Depends(ai_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    d = _doc(db, sid, user, did)
    return files.serve(sid, d.file_path, d.content_type, d.name)


@router.delete("/documents/{did}", status_code=204)
def delete_document(did: int, user: User = Depends(ai_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    d = _doc(db, sid, user, did)
    db.execute(delete(AiChunk).where(AiChunk.document_id == d.id))
    for m in db.scalars(select(AiMessage).where(AiMessage.attachment_id == d.id)):
        m.attachment_id = None
    path = d.file_path
    db.delete(d)
    db.commit()
    files.remove(path)
