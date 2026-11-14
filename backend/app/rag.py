"""Retrieval over a user's uploaded notes: chunk -> embed (via the `Embedder` interface) -> cosine top-k.
Vectors live in `ai_chunks.embedding` (JSON). On Postgres this becomes pgvector; the call sites stay the same."""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai import Embedder, Passage, cosine
from .models import AiChunk, AiDocument

CHUNK_CHARS = 600
MIN_SCORE = 0.12  # below this a chunk is treated as unrelated (hash embeddings only match shared words)


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Greedy paragraph/sentence packing into ~size-char chunks."""
    units = [u.strip() for u in re.split(r"\n{2,}|(?<=[.!?।])\s+", text) if u.strip()]
    chunks, cur = [], ""
    for u in units:
        if cur and len(cur) + len(u) + 1 > size:
            chunks.append(cur)
            cur = ""
        while len(u) > size:  # one huge unit: hard split
            chunks.append(u[:size])
            u = u[size:]
        cur = f"{cur} {u}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def index_document(db: Session, school_id: int, user_id: int, doc: AiDocument, embedder: Embedder, max_chunks: int = 400) -> int:
    chunks = chunk_text(doc.text)[:max_chunks]
    vecs = embedder.embed(chunks) if chunks else []
    for i, (t, v) in enumerate(zip(chunks, vecs)):
        db.add(AiChunk(school_id=school_id, created_by=user_id, document_id=doc.id, user_id=user_id, position=i, text=t,
                       embedding=v, embed_model=embedder.name))  # fmt: skip
    doc.chunk_count = len(chunks)
    return len(chunks)


def retrieve(db: Session, school_id: int, user_id: int, query: str, embedder: Embedder, k: int = 3) -> list[Passage]:
    """Top-k chunks of THIS user's documents (never anyone else's) scoring above MIN_SCORE."""
    rows = db.execute(
        select(AiChunk, AiDocument.name).join(AiDocument, AiDocument.id == AiChunk.document_id).where(
            AiChunk.school_id == school_id, AiChunk.user_id == user_id, AiChunk.embed_model == embedder.name)
    ).all()  # fmt: skip
    if not rows:
        return []
    qv = embedder.embed([query])[0]
    scored = sorted(((cosine(qv, c.embedding), c, name) for c, name in rows), key=lambda x: -x[0])
    return [Passage(document=name, text=c.text, score=round(s, 3), document_id=c.document_id) for s, c, name in scored[:k] if s >= MIN_SCORE]
