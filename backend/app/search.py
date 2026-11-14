"""Hybrid retrieval: BM25 (keywords) + embedding cosine (meaning), then a light rerank.

score = 0.55 * bm25_normalised + 0.45 * cosine, then rerank boosts passages that cover more of the query's distinct
terms and school-approved material. Works on any list of (id, label, text) units, so it serves both a user's private
notes and the school library."""
import math
import re
from collections import Counter
from dataclasses import dataclass

from .ai import Embedder, _tokens, cosine

K1, B = 1.4, 0.75


@dataclass
class Hit:
    ref: object
    label: str
    text: str
    score: float
    bm25: float = 0.0
    cos: float = 0.0


def bm25_scores(query_toks: list[str], docs: list[list[str]]) -> list[float]:
    n = len(docs)
    if not n or not query_toks:
        return [0.0] * n
    avg = sum(len(d) for d in docs) / n or 1.0
    df = Counter(t for d in docs for t in set(d))
    out = []
    for d in docs:
        tf = Counter(d)
        s = 0.0
        for t in set(query_toks):
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * len(d) / avg))
        out.append(s)
    return out


def chunk(text: str, size: int = 700) -> list[str]:
    parts, cur = [], ""
    for u in re.split(r"\n{2,}|(?<=[.!?।])\s+", text):
        u = u.strip()
        if not u:
            continue
        if cur and len(cur) + len(u) > size:
            parts.append(cur)
            cur = ""
        cur = f"{cur} {u}".strip()
    if cur:
        parts.append(cur)
    return parts


def hybrid(query: str, units: list[tuple[object, str, str, bool]], embedder: Embedder | None, k: int = 4,
           min_score: float = 0.18) -> list[Hit]:
    """units = [(ref, label, text, approved)]. Returns top-k hits above min_score."""
    if not units:
        return []
    qt = _tokens(query)
    toks = [_tokens(t) for _, _, t, _ in units]
    bm = bm25_scores(qt, toks)
    mx = max(bm) or 1.0
    cos = [0.0] * len(units)
    if embedder is not None:
        try:
            vecs = embedder.embed([query] + [t for _, _, t, _ in units])
            cos = [max(0.0, cosine(vecs[0], v)) for v in vecs[1:]]
        except Exception:  # provider hiccup: keyword search alone still works
            cos = [0.0] * len(units)
    hits = []
    qset = set(qt)
    for i, (ref, label, text, approved) in enumerate(units):
        base = 0.55 * (bm[i] / mx) + 0.45 * cos[i]
        cover = len(qset & set(toks[i])) / (len(qset) or 1)
        score = base * (0.6 + 0.4 * cover) * (1.1 if approved else 1.0)  # rerank
        if bm[i] > 0 or cos[i] > 0.25:
            hits.append(Hit(ref, label, text, round(score, 4), round(bm[i], 3), round(cos[i], 3)))
    hits.sort(key=lambda h: -h.score)
    return [h for h in hits[:k] if h.score >= min_score]
