"""AI interface for Phase 4 (blueprint §14): robo assistant, AI Chat, flashcard writing and text embeddings.

Callers depend on the `Tutor` and `Embedder` protocols; swap `get_tutor()` / `get_embedder()` to return a real provider
later (config `EDUNEST_AI_PROVIDER`). Same pattern as `llm.py`. Privacy rule from the blueprint: only academic text crosses
this boundary, never student/teacher names, phones or ids — the dataclasses below simply have no field for them.

`StubTutor` / `HashEmbedder` are deterministic and offline. They are NOT an LLM: the stub reuses the quiz's own
explanation, extracts sentences from uploaded notes, and says plainly when it cannot answer. Everything around them
(retrieval, caching, limits, scheduling, UI) is real."""
import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import HTTPException, status

from .config import get_settings

LANGS = ("en", "te", "hi", "ml", "ta")


# ------------------------------------------------------------------ data crossing the boundary
@dataclass
class WrongAnswerCtx:
    question: str
    qtype: str
    options: list[str]
    correct: str  # already rendered as text (e.g. the option's text, "True", "Paris")
    given: str  # what the student answered, rendered as text ("" = left blank)
    topic: str = ""
    explanation: str = ""  # teacher-written explanation, may be empty
    lang: str = "en"


@dataclass
class Passage:
    document: str
    text: str
    score: float = 0.0
    document_id: int = 0


@dataclass
class Attachment:
    name: str
    content_type: str
    text: str  # "" when nothing could be read (image, scanned PDF)


@dataclass
class ChatReply:
    text: str
    used_passages: list[Passage] = field(default_factory=list)


@dataclass
class CardDraft:
    front: str
    back: str
    topic: str = ""


class Tutor(Protocol):
    name: str

    def explain(self, ctx: WrongAnswerCtx) -> str: ...
    def why_wrong(self, ctx: WrongAnswerCtx) -> str: ...
    def next_suggestion(self, topic: str, has_question: bool, lang: str = "en") -> str: ...
    def chat(self, question: str, history: list[tuple[str, str]], passages: list[Passage], attachments: list[Attachment],
             lang: str = "en") -> ChatReply: ...
    def make_cards(self, text: str, topic: str = "", max_cards: int = 10) -> list[CardDraft]: ...


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


# ------------------------------------------------------------------ offline embedder
_STOP = set("a an and are as at be by for from has have in is it its of on or that the this to was were will with what which who how why "
            "when where do does did i you he she we they me my your our their can could should would about into than then there".split())
_DIM = 256


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.casefold(), re.UNICODE) if t not in _STOP and len(t) > 1]


class HashEmbedder:
    """Hashed bag-of-words vectors (L2-normalised). Deterministic, offline, works for Telugu/Hindi tokens too, but only
    matches shared words, not meaning. A real embedding model replaces it behind the same interface."""

    name = "hash-256"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * _DIM
            for tok in _tokens(t):
                h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "big")  # md5: stable across processes (hash() is not)
                v[h % _DIM] += 1.0 if (h >> 31) & 1 else -1.0  # signed hashing keeps collisions unbiased
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([round(x / norm, 5) for x in v])
        return out


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # both unit length


# ------------------------------------------------------------------ offline tutor
_DEF = re.compile(r"^(?P<term>[A-Z][\w\s\-']{1,60}?)\s+(?P<verb>is|are|means|refers to)\s+(?P<rest>.{8,300})$")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?।])\s+|\n+", text) if len(s.strip()) > 15]


class StubTutor:
    name = "stub"

    # -- robo assistant
    def explain(self, ctx: WrongAnswerCtx) -> str:
        parts = [f"The correct answer is: {ctx.correct}."]
        if ctx.explanation:
            parts.append(ctx.explanation)
        else:
            parts.append("Your teacher has not added an explanation for this question yet. Re-read the question and compare "
                         "each option with the correct answer to see what makes it right.")
        if ctx.topic:
            parts.append(f"Topic to revise: {ctx.topic}.")
        return "\n\n".join(parts)

    def why_wrong(self, ctx: WrongAnswerCtx) -> str:
        given = ctx.given or "nothing (the question was left blank)"
        parts = [f"You answered: {given}.", f"The correct answer is: {ctx.correct}."]
        if ctx.given and ctx.qtype == "mcq":
            parts.append("Check whether your choice sounds similar to the right one but differs in one key detail. Look for the "
                         "exact words in the question that rule your option out.")
        elif not ctx.given:
            parts.append("A blank answer scores zero, so it is always worth making your best guess next time.")
        if ctx.explanation:
            parts.append(ctx.explanation)
        return "\n\n".join(parts)

    def next_suggestion(self, topic: str, has_question: bool, lang: str = "en") -> str:
        t = f" on {topic}" if topic else ""
        if has_question:
            return f"Let's practise with another question{t}. Take your time, then check your answer."
        return (f"There is no other question{t} to practise yet. Re-read the explanation, then try the same question again "
                "later, or turn this mistake into a flashcard.")

    # -- AI chat
    def chat(self, question, history, passages, attachments, lang="en") -> ChatReply:
        unread = [a for a in attachments if not a.text]
        if passages:
            lines = ["Here is what your uploaded notes say about this:"]
            for p in passages:
                best = max(_sentences(p.text) or [p.text], key=lambda s: len(set(_tokens(s)) & set(_tokens(question))))
                lines.append(f"• {best}  — {p.document}")
            return ChatReply("\n\n".join(lines), passages)
        msg = ("I am running in offline demo mode, so I can only answer from notes you have uploaded, and I found nothing "
               "relevant to that question. Upload a PDF or text file of your notes, then ask again.")
        if unread:
            msg += (f" I could not read the text of {', '.join(a.name for a in unread)} (images and scanned PDFs need OCR, "
                    "which is not connected yet).")
        return ChatReply(msg)

    # -- flashcards
    def make_cards(self, text: str, topic: str = "", max_cards: int = 10) -> list[CardDraft]:
        cards: list[CardDraft] = []
        for s in _sentences(text):
            m = _DEF.match(s.rstrip("."))
            if not m:
                continue
            term = re.sub(r"^(?:the|a|an)\s+", "", m["term"].strip(), flags=re.I)
            front = f"What {'are' if m['verb'] == 'are' else 'is'} {term}?"
            cards.append(CardDraft(front, s, topic))
            if len(cards) >= max_cards:
                break
        return cards


# ------------------------------------------------------------------ provider selection
class ProviderTutor(StubTutor):
    """Real LLM behind the same Tutor interface (EduNest 2.0). Any provider failure falls back to the offline stub."""

    def __init__(self, provider: str):
        self.name = provider

    def _ask(self, extra: str, prompt: str, lang: str, history: list[tuple[str, str]] | None = None) -> str | None:
        from . import providers

        try:
            return providers.complete(providers.system_prompt(extra, lang), [*(history or []), ("user", prompt)])
        except providers.LLMError:
            return None

    def explain(self, ctx: WrongAnswerCtx) -> str:
        p = (f"Question: {ctx.question}\nOptions: {ctx.options}\nCorrect answer: {ctx.correct}\nTopic: {ctx.topic}\n"
             f"Teacher explanation: {ctx.explanation or '(none)'}\nExplain the correct answer simply, with one example, then "
             "list 2 focus points to revise.")
        return self._ask("You are explaining a quiz answer to a student.", p, ctx.lang) or super().explain(ctx)

    def why_wrong(self, ctx: WrongAnswerCtx) -> str:
        p = (f"Question: {ctx.question}\nOptions: {ctx.options}\nStudent answered: {ctx.given or '(blank)'}\n"
             f"Correct: {ctx.correct}\nExplain kindly why the student's answer is not right and what clue in the question "
             "points to the correct one. Encourage them.")
        return self._ask("You are a patient tutor.", p, ctx.lang) or super().why_wrong(ctx)

    def chat(self, question, history, passages, attachments, lang="en") -> ChatReply:
        ctx = "\n\n".join(f"[source: {p.document}]\n{p.text}" for p in passages)
        att = "\n\n".join(f"[attached: {a.name}]\n{a.text[:6000]}" for a in attachments if a.text)
        prompt = question
        if ctx or att:
            prompt = f"School material:\n{ctx}\n\n{att}\n\nQuestion: {question}"
        out = self._ask("Ground your answer in the school material when it is relevant and cite it.", prompt, lang, history)
        return ChatReply(out, passages) if out else super().chat(question, history, passages, attachments, lang)

    def make_cards(self, text: str, topic: str = "", max_cards: int = 10) -> list[CardDraft]:
        import json as _json

        out = self._ask("Return ONLY a JSON list of objects with keys front and back.",
                        f"Write up to {max_cards} short revision flashcards from this text:\n{text[:8000]}", "en")
        try:
            data = _json.loads(out[out.index("["): out.rindex("]") + 1]) if out else []
            cards = [CardDraft(str(c["front"])[:300], str(c["back"])[:600], topic) for c in data if c.get("front") and c.get("back")]
            return cards[:max_cards] or super().make_cards(text, topic, max_cards)
        except (ValueError, KeyError, TypeError, AttributeError):
            return super().make_cards(text, topic, max_cards)


class ProviderEmbedder:
    """OpenAI-compatible embeddings; falls back to hashing for a batch if the call fails (chunks keep their model tag)."""

    def __init__(self, model: str):
        self.name = model[:40]

    def embed(self, texts: list[str]) -> list[list[float]]:
        from . import providers

        vecs = providers.embed_texts(texts)
        if vecs is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Embedding provider unavailable")
        return vecs


def _check_provider() -> None:
    from . import providers

    provider = get_settings().ai_provider
    if provider != "stub" and not providers.configured():
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"AI provider '{provider}' is not configured (set EDUNEST_AI_API_KEY)")


def get_tutor() -> Tutor:
    _check_provider()
    s = get_settings()
    return StubTutor() if s.ai_provider == "stub" else ProviderTutor(s.ai_provider)


def get_embedder() -> Embedder:
    _check_provider()
    s = get_settings()
    if s.ai_provider == "openai" and s.ai_embed_model:
        return ProviderEmbedder(s.ai_embed_model)
    return HashEmbedder()
