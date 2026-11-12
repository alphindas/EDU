"""LLM interface for AI features. Phase 3 only needs question generation (blueprint §14: "Quiz from teacher PDF").

Callers depend on `QuestionGenerator`; swap `get_generator()` to return a real provider later. Privacy rule from the
blueprint: only academic text crosses this boundary, never student/teacher names, phones or ids.

`StubGenerator` is a deterministic, offline parser: it recognises numbered questions with A)-D) options and an optional
`Answer:` / `Explanation:` line. It is NOT an LLM; anything it cannot parse is skipped and the teacher adds it by hand."""
import re
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import HTTPException, status

from .config import get_settings


@dataclass
class QuestionDraft:
    qtype: str  # mcq | true_false | fill_blank | descriptive
    text: str
    options: list[str] = field(default_factory=list)
    answer: object = None
    explanation: str = ""
    topic: str = ""
    difficulty: str = "medium"
    marks: float = 1.0


class QuestionGenerator(Protocol):
    def generate(self, text: str, max_questions: int = 20) -> list[QuestionDraft]: ...


_Q_START = re.compile(r"^\s*(?:Q(?:uestion)?\.?\s*)?(\d{1,3})\s*[.)]\s+(.*)$", re.I)
_OPT = re.compile(r"^\s*\(?([A-Da-d])[.)]\s+(.*)$")
_ANS = re.compile(r"^\s*(?:ans(?:wer)?|correct answer)\s*[:\-]\s*(.*)$", re.I)
_EXP = re.compile(r"^\s*explanation\s*[:\-]\s*(.*)$", re.I)
_TOPIC = re.compile(r"^\s*(?:topic|chapter)\s*[:\-]\s*(.*)$", re.I)


class StubGenerator:
    def generate(self, text: str, max_questions: int = 20) -> list[QuestionDraft]:
        blocks: list[list[str]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            m = _Q_START.match(line)
            if m:
                blocks.append([m.group(2).strip()])
            elif blocks:
                blocks[-1].append(line.strip())
        out: list[QuestionDraft] = []
        for b in blocks:
            q = self._parse(b)
            if q:
                out.append(q)
            if len(out) >= max_questions:
                break
        return out

    @staticmethod
    def _parse(lines: list[str]) -> QuestionDraft | None:
        stem: list[str] = []
        opts: list[tuple[str, str]] = []
        ans = exp = topic = ""
        for ln in lines:
            if m := _ANS.match(ln):
                ans = m.group(1).strip()
            elif m := _EXP.match(ln):
                exp = m.group(1).strip()
            elif m := _TOPIC.match(ln):
                topic = m.group(1).strip()
            elif m := _OPT.match(ln):
                opts.append((m.group(1).upper(), m.group(2).strip()))
            elif opts and not ans:
                opts[-1] = (opts[-1][0], opts[-1][1] + " " + ln)  # wrapped option line
            else:
                stem.append(ln)
        text = " ".join(stem).strip()
        if not text:
            return None
        base = dict(explanation=exp, topic=topic)
        if len(opts) >= 2:
            letters = [k for k, _ in opts]
            idx = letters.index(ans[:1].upper()) if ans and ans[:1].upper() in letters else None
            return QuestionDraft("mcq", text, [v for _, v in opts], idx, **base)
        low = ans.lower()
        if low in ("true", "false", "t", "f") or re.search(r"true\s*(or|/)\s*false", text, re.I):
            return QuestionDraft("true_false", text, [], low.startswith("t") if low else None, **base)
        if "___" in text:
            return QuestionDraft("fill_blank", text, [], [a.strip() for a in ans.split("|") if a.strip()], **base)
        return QuestionDraft("descriptive", text, [], ans, marks=2.0, **base)


def get_generator() -> QuestionGenerator:
    provider = get_settings().llm_provider
    if provider == "stub":
        return StubGenerator()
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"LLM provider '{provider}' is not configured")


def pdf_text(path: str, max_pages: int = 30) -> str:
    """Extract text from a stored PDF. Scanned PDFs (no text layer) yield '' -> caller reports it."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    except (PyPdfError, ValueError, OSError, KeyError):
        return ""
