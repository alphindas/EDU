"""CHITTI 2.0: the ONE shared AI engine behind every portal.

Each role gets different modes, knowledge sources and permissions (enforced in routers/chitti.py), but the engine is
the same. When a real LLM is configured (providers.py) answers come from it, grounded in school material. Without a
key, CHITTI runs in offline mode: built-in starter topics (kb.py), a step-by-step maths solver (sympy), rule-based
English coaching, and keyword+hash hybrid search over the school library. Offline answers are honest about their
limits and never invent facts."""
import json
import random
import re
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import kb, providers
from .ai import Embedder
from .models_v2 import Resource
from .search import Hit, chunk, hybrid

MODES = ("study_buddy", "doubt_solver", "english", "aptitude", "puzzle", "career", "parent", "lesson_plan")
MODE_PROMPTS = {
    "study_buddy": "Mode: Study Buddy. Teach the idea step by step with a simple example, then ask one quick check question.",
    "doubt_solver": "Mode: Doubt Solver. Solve the doubt step by step, number the steps, and give the final answer clearly.",
    "english": "Mode: English Chitti. Be a friendly English coach: correct grammar gently, explain each fix, suggest better words.",
    "aptitude": "Mode: Aptitude Chitti. Give logical/numerical reasoning practice with the method explained after each answer.",
    "puzzle": "Mode: Puzzle Master. Pose fun, age-appropriate riddles and logic puzzles; give hints before answers.",
    "career": "Mode: Career Chitti. Offer career guidance (never predictions): options, subjects to focus on, next steps.",
    "parent": "Mode: Parent helper. Explain today's school topics simply for a parent, suggest home activities and practice, "
              "using only school-approved syllabus material. Do not share any other child's information.",
    "lesson_plan": "Mode: Teacher assistant. Draft lesson plans, revision material and question sets aligned to the syllabus.",
}


def level_text(class_name: str | None) -> str:
    if not class_name or not class_name.isdigit():
        return ""
    n = int(class_name)
    return f"a Class {n} school student (about {n + 5} years old)"


# ------------------------------------------------------------------ school library search
def school_hits(db: Session, sid: int, query: str, class_id: int | None, embedder: Embedder | None, k: int = 4) -> list[Hit]:
    q = select(Resource).where(Resource.school_id == sid, Resource.approved.is_(True))
    if class_id:
        q = q.where(or_(Resource.class_id == class_id, Resource.class_id.is_(None)))
    units = []
    for r in db.scalars(q.limit(200)):
        chapters = r.chapters or ([{"title": r.title, "text": r.text}] if r.text else [])
        for ci, ch in enumerate(chapters):
            for part in chunk(ch.get("text", ""))[:40]:
                label = f"{r.title} · {ch.get('title') or f'Chapter {ci + 1}'}"
                units.append(({"resource_id": r.id, "chapter": ci}, label, part, r.approved))
    return hybrid(query, units, embedder, k=k)


def _sources(hits: list[Hit]) -> list[dict]:
    return [{"name": h.label, "snippet": h.text[:220], **h.ref} for h in hits]


# ------------------------------------------------------------------ topic search
def topic_search(db: Session, sid: int, query: str, lang: str, class_name: str | None, class_id: int | None,
                 embedder: Embedder | None) -> dict:
    hits = school_hits(db, sid, query, class_id, embedder)
    found = kb.find(query)
    title = found[1]["title"] if found else query.strip().title()
    videos = kb.youtube_links(found[1]["videos"] if found else [f"{query} explained", f"{query} for students"], lang)
    practice = [dict(q) for q in found[1]["questions"]] if found else []
    out = {"title": title, "explanation": "", "example": "", "points": [], "videos": videos, "practice": practice,
           "sources": _sources(hits), "provider": providers.provider_name(), "found": bool(found or hits)}  # fmt: skip
    if providers.configured():
        ctx = "\n\n".join(f"[source: {h.label}]\n{h.text}" for h in hits)
        prompt = (f"Topic: {query}\nSchool material:\n{ctx or '(none)'}\n\nReturn ONLY JSON with keys: explanation (simple, "
                  "<=120 words), example (one everyday example), points (3-4 key facts), practice (4 MCQs as objects "
                  "{q, o (4 options), a (index of correct option), e (one-line explanation)}).")
        try:
            raw = providers.complete(providers.system_prompt("", lang, level_text(class_name)), [("user", prompt)], max_tokens=1200)
            data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            out.update(explanation=str(data.get("explanation", "")), example=str(data.get("example", "")),
                       points=[str(p) for p in data.get("points", [])][:5])  # fmt: skip
            qs = [q for q in data.get("practice", []) if isinstance(q, dict) and len(q.get("o", [])) >= 2
                  and isinstance(q.get("a"), int) and 0 <= q["a"] < len(q["o"])]  # fmt: skip
            out["practice"] = qs[:6] or practice
            return out
        except (providers.LLMError, ValueError, TypeError):
            pass  # fall through to offline content
    if found:
        t = found[1]
        out.update(explanation=t["explain"], example=t["example"], points=t["points"])
    elif hits:
        out.update(explanation=hits[0].text, points=[h.text[:160] for h in hits[1:3]])
    else:
        out["explanation"] = ("I'm not sure about this topic yet. I couldn't find it in your school library or my starter topics. "
                              "Try the video links, ask your teacher to upload notes, or connect a full AI model.")
    return out


# ------------------------------------------------------------------ photo doubt (OCR + solver)
def ocr_image(path: str, langs: str) -> str:
    try:
        import pytesseract
        from PIL import Image, ImageOps

        have = set(pytesseract.get_languages(config=""))
        multi = "+".join(l for l in langs.split("+") if l in have) or "eng"
        with Image.open(path) as im:
            g = ImageOps.grayscale(ImageOps.exif_transpose(im))
            if g.width < 1000:
                g = g.resize((g.width * 2, g.height * 2))
            eng = pytesseract.image_to_string(g, lang="eng").strip()
            if multi == "eng":
                return eng
            other = pytesseract.image_to_string(g, lang=multi).strip()
            letters = [c for c in other if c.isalpha()]
            indic = sum(1 for c in letters if ord(c) > 0x0900)
            # Indic-script page -> keep the multi-language read; otherwise English reads digits and maths symbols better
            return other if letters and indic / len(letters) >= 0.3 else eng
    except Exception:  # tesseract binary missing / unreadable image
        return ""


_MATH_CLEAN = [("×", "*"), ("÷", "/"), ("−", "-"), ("–", "-"), ("^", "**"), ("²", "**2"), ("³", "**3")]


def _expr(s: str) -> str:
    for a, b in _MATH_CLEAN:
        s = s.replace(a, b)
    s = re.sub(r"(\d)\s*([a-z(])", r"\1*\2", s)  # 2x -> 2*x, 3(… -> 3*(…
    return s


def solve_offline(text: str) -> dict | None:
    """Step-by-step for: % of, linear/quadratic equations in x, plain arithmetic. None if not recognised."""
    import sympy as sp

    t = text.strip().lower().replace("solve", "").replace("find x", "").replace("?", "").strip(" :.")
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", t)
    if m:
        p, n = float(m[1]), float(m[2])
        ans = p * n / 100
        return {"topic": "percentage", "answer": f"{ans:g}", "steps": [
            f"'{p:g}% of {n:g}' means {p:g}/100 × {n:g}.", f"{p:g} ÷ 100 = {p / 100:g}.", f"{p / 100:g} × {n:g} = {ans:g}."]}
    m = re.search(r"([0-9a-z+\-*/().^²³×÷−–\s]+)=([0-9a-z+\-*/().^²³×÷−–\s]+)", t)
    if m and re.search(r"[a-z]", m[0]):
        var = sorted(set(re.findall(r"[a-z]", m[0])))
        if len(var) == 1:
            x = sp.Symbol(var[0])
            try:
                lhs = sp.sympify(_expr(m[1]), locals={var[0]: x})
                rhs = sp.sympify(_expr(m[2]), locals={var[0]: x})
            except (sp.SympifyError, SyntaxError, TypeError):
                return None
            expr = sp.expand(lhs - rhs)
            deg = sp.degree(expr, x) if expr.has(x) else 0
            sols = sp.solve(sp.Eq(lhs, rhs), x)
            if not sols:
                return {"topic": "equation", "answer": "no solution", "steps": ["Simplifying both sides gives a contradiction."]}
            if deg == 1:
                a, b = sp.Poly(expr, x).all_coeffs()
                steps = [f"Write the equation: {sp.sstr(lhs)} = {sp.sstr(rhs)}.",
                         f"Bring every {var[0]} term to the left and numbers to the right: {sp.sstr(a * x)} = {sp.sstr(-b)}.",
                         f"Divide both sides by {sp.sstr(a)}: {var[0]} = {sp.sstr(-b)}/{sp.sstr(a)} = {sp.sstr(sols[0])}.",
                         f"Check: put {var[0]} = {sp.sstr(sols[0])} back in; both sides equal {sp.sstr(lhs.subs(x, sols[0]))}."]
                return {"topic": "linear equations", "answer": f"{var[0]} = {sp.sstr(sols[0])}", "steps": steps}
            if deg == 2:
                a, b, c = sp.Poly(expr, x).all_coeffs()
                d = b * b - 4 * a * c
                steps = [f"Rewrite as {sp.sstr(expr)} = 0, so a = {a}, b = {b}, c = {c}.",
                         f"Discriminant D = b² − 4ac = {sp.sstr(d)}.",
                         f"x = (−b ± √D) / 2a = (−({b}) ± √{sp.sstr(d)}) / {2 * a}.",
                         "So " + " or ".join(f"{var[0]} = {sp.sstr(s)}" for s in sols) + "."]
                return {"topic": "quadratic equations", "answer": ", ".join(sp.sstr(s) for s in sols), "steps": steps}
            return {"topic": "equation", "answer": ", ".join(sp.sstr(s) for s in sols), "steps": ["Solved symbolically."]}
    expr_m = re.fullmatch(r"[0-9+\-*/().^²³×÷−–\s]+", t)
    if expr_m and re.search(r"\d\s*[+\-*/×÷^−–]\s*\d", t):
        try:
            e = sp.sympify(_expr(t), evaluate=False)
            val = sp.nsimplify(sp.sympify(_expr(t)))
        except (sp.SympifyError, SyntaxError, TypeError, ZeroDivisionError):
            return None
        return {"topic": "arithmetic", "answer": sp.sstr(val), "steps": [
            f"Expression: {sp.sstr(e)}.", "Use BODMAS: Brackets, Orders (powers), Division/Multiplication, then Addition/Subtraction.",
            f"Result = {sp.sstr(val)}" + (f" ≈ {float(val):.4g}" if not val.is_integer else "") + "."]}
    return None


def solve(text: str, lang: str, class_name: str | None, image: tuple[bytes, str] | None = None) -> dict:
    if providers.configured():
        prompt = ("Solve this school question step by step. Return ONLY JSON: {\"topic\": short topic, \"steps\": [strings], "
                  f"\"answer\": final answer, \"explanation\": one simple paragraph}}.\nQuestion: {text or '(see image)'}")
        try:
            raw = providers.complete(providers.system_prompt(MODE_PROMPTS["doubt_solver"], lang, level_text(class_name)),
                                     [("user", prompt)], image=image, max_tokens=1200)  # fmt: skip
            d = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            return {"topic": str(d.get("topic", "")), "steps": [str(s) for s in d.get("steps", [])], "answer": str(d.get("answer", "")),
                    "explanation": str(d.get("explanation", "")), "provider": providers.provider_name()}  # fmt: skip
        except (providers.LLMError, ValueError, TypeError):
            pass
    r = solve_offline(text) if text else None
    if r:
        return {**r, "explanation": "", "provider": "stub"}
    found = kb.find(text or "")
    if found:
        t = found[1]
        return {"topic": t["title"], "steps": [t["explain"], *t["points"]], "answer": "", "explanation": t["example"], "provider": "stub"}
    return {"topic": "", "steps": [], "answer": "", "provider": "stub",
            "explanation": "I'm not sure how to solve this one in offline mode. I can solve percentages, equations and "
                           "arithmetic step by step, and explain my starter topics. Ask your teacher, or connect a full AI model."}


def _shuffle(rnd: random.Random, items: list[dict]) -> list[dict]:
    for q in items:
        right = q["o"][q["a"]]
        rnd.shuffle(q["o"])
        q["a"] = q["o"].index(right)
    return items


def similar_questions(topic: str, text: str, n: int = 5, seed: int | None = None) -> list[dict]:
    """Practice set for 'Practice similar questions': generated maths items, else starter-topic MCQs."""
    rnd = random.Random(seed)
    out: list[dict] = []
    t = (topic or "").lower()
    if "linear" in t:
        for _ in range(n):
            a, x, b = rnd.randint(2, 9), rnd.randint(1, 12), rnd.randint(1, 20)
            c = a * x + b
            opts = sorted({x, x + 1, x - 1 if x > 1 else x + 3, x + 2})
            out.append({"q": f"Solve: {a}x + {b} = {c}", "o": [str(o) for o in opts], "a": opts.index(x),
                        "e": f"{a}x = {c} − {b} = {c - b}, so x = {c - b}/{a} = {x}."})
    elif "percent" in t:
        for _ in range(n):
            p, m = rnd.choice([5, 10, 12, 15, 20, 25, 40, 50]), rnd.choice([40, 60, 80, 120, 150, 200, 240, 300])
            ans = p * m // 100 if p * m % 100 == 0 else p * m / 100
            opts = sorted({ans, ans + 5, ans * 2, max(1, ans - 3)})
            out.append({"q": f"What is {p}% of {m}?", "o": [f"{o:g}" for o in opts], "a": opts.index(ans), "e": f"{p}/100 × {m} = {ans:g}."})
    elif "arith" in t:
        for _ in range(n):
            a, b, c = rnd.randint(2, 20), rnd.randint(2, 9), rnd.randint(1, 30)
            ans = a + b * c
            opts = sorted({ans, (a + b) * c, ans + 1, ans - 2})
            out.append({"q": f"{a} + {b} × {c} = ?", "o": [str(o) for o in opts], "a": opts.index(ans), "e": f"Multiply first: {b}×{c}={b * c}, then +{a}."})
    if out:
        return _shuffle(rnd, out)
    found = kb.find(topic or text or "")
    return [dict(q) for q in found[1]["questions"]][:n] if found else []


# ------------------------------------------------------------------ English Chitti (offline coach)
_RULES = [
    (r"\bi\b", "I", "The word 'I' is always a capital letter."),
    (r"\bI (goes|does|has)\b", None, "With 'I' use the base verb: I go, I do, I have."),
    (r"\b(he|she|it) don't\b", r"\1 doesn't", "With he/she/it use 'doesn't'."),
    (r"\b(he|she|it) have\b", r"\1 has", "With he/she/it use 'has'."),
    (r"\b(they|we|you) was\b", r"\1 were", "With they/we/you use 'were'."),
    (r"\b(i|I) is\b", "I am", "Use 'I am'."),
    (r"\bshould of\b", "should have", "'should of' is a common mistake for 'should have'."),
    (r"\bcould of\b", "could have", "'could of' → 'could have'."),
    (r"\bwould of\b", "would have", "'would of' → 'would have'."),
    (r"\bmore better\b", "better", "'better' already means 'more good'."),
    (r"\bmost best\b", "best", "'best' already means 'most good'."),
    (r"\ba ([aeiou]\w*)", r"an \1", "Use 'an' before a vowel sound."),
    (r"\bdidn't (went|ate|came|saw|did|took|gave|wrote)\b", None, "After 'didn't' use the base verb (didn't go, didn't eat)."),
    (r"\bmuch (people|students|friends|books|things)\b", r"many \1", "Use 'many' with things you can count."),
    (r"\bdiscuss about\b", "discuss", "'discuss' doesn't need 'about'."),
    (r"\breturn back\b", "return", "'return' already means 'go back'."),
    (r"\bcousin brother\b|\bcousin sister\b", "cousin", "In English just say 'cousin'."),
    (r"\bdo one thing\b", "here's an idea", "'Do one thing' is Indian English; try 'here's an idea'."),
    (r"\bkindly do the needful\b", "please help with this", "A clearer, modern phrase."),
    (r"\bmyself (\w+)\b(?= and| here|,|\.)", r"I am \1", "Introduce yourself as 'I am …' or 'My name is …'."),
]
_BASE = {"went": "go", "ate": "eat", "came": "come", "saw": "see", "did": "do", "took": "take", "gave": "give", "wrote": "write"}
_VOCAB = {"very good": "excellent", "very bad": "terrible", "very big": "huge", "very small": "tiny", "very happy": "delighted",
          "very sad": "heartbroken", "very tired": "exhausted", "very hungry": "starving", "nice": "pleasant", "good": "great",
          "said": "explained", "big": "large", "thing": "item", "got": "received", "very important": "essential",
          "very fast": "rapid", "very scared": "terrified", "very cold": "freezing", "very hot": "scorching"}
FILLERS = re.compile(r"\b(um+|uh+|erm|hmm+|you know|basically|actually)\b|\blike,", re.I)
_I_BASE = {"goes": "go", "does": "do", "has": "have"}


def _fix_none(pat: str, m: re.Match) -> str:
    if pat.startswith(r"\bI "):
        return "I " + _I_BASE[m.group(1)]
    return "didn't " + _BASE.get(m.group(1).lower(), m.group(1))


def english_check(text: str, seconds: float = 0) -> dict:
    corrected, issues = text, []
    for pat, rep, why in _RULES:
        for m in list(re.finditer(pat, corrected, flags=0 if pat in (r"\bi\b", r"\bI (goes|does|has)\b") else re.I)):
            wrong = m.group(0)
            if rep is None:  # didn't + past -> base / I + base
                right = _fix_none(pat, m)
            else:
                right = m.expand(rep) if "\\" in rep else rep
            if wrong != right:
                issues.append({"wrong": wrong, "right": right, "why": why})
        if rep is None:
            corrected = re.sub(pat, lambda m, p=pat: _fix_none(p, m), corrected, flags=0 if pat.startswith(r"\bI ") else re.I)
        elif pat == r"\bi\b":
            corrected = re.sub(pat, rep, corrected)
        else:
            corrected = re.sub(pat, rep, corrected, flags=re.I)
    sents = [s for s in re.split(r"(?<=[.!?])\s+", corrected.strip()) if s]
    fixed = []
    for s in sents:
        if s and s[0].islower():
            issues.append({"wrong": s.split()[0], "right": s.split()[0].capitalize(), "why": "Start a sentence with a capital letter."})
            s = s[0].upper() + s[1:]
        fixed.append(s)
    corrected = " ".join(fixed)
    if corrected and corrected[-1] not in ".!?":
        corrected += "."
        issues.append({"wrong": "(end)", "right": ".", "why": "End a sentence with a full stop, ? or !."})
    vocab = [{"word": k, "better": v} for k, v in _VOCAB.items() if re.search(rf"\b{k}\b", text, re.I)][:5]
    words = len(re.findall(r"[A-Za-z']+", text))
    fillers = len(FILLERS.findall(text))
    wpm = round(words / (seconds / 60), 1) if seconds > 3 else 0.0
    acc = max(0.0, 100 - 12 * len(issues) - 4 * fillers)
    pace = 100.0 if not wpm else max(0.0, 100 - abs(wpm - 120) * 0.8)
    score = round(acc if not wpm else 0.7 * acc + 0.3 * pace, 1)
    tips = []
    if fillers:
        tips.append("Try pausing silently instead of saying 'um' or 'like'. Pauses sound confident!")
    if wpm and wpm < 80:
        tips.append("You can speak a little faster. Aim for about 110–140 words per minute.")
    if wpm and wpm > 170:
        tips.append("Slow down a little so every word is clear.")
    if words and words < 12:
        tips.append("Try saying a bit more: add a reason or an example ('because…', 'for example…').")
    if not issues:
        tips.append("Great grammar! Now try a longer answer with a linking word like 'however' or 'therefore'.")
    return {"corrected": corrected, "issues": issues, "vocab": vocab, "tips": tips, "words": words, "fillers": fillers,
            "wpm": wpm, "score": score}  # fmt: skip


def pronounce_compare(target: str, heard: str) -> dict:
    import difflib

    tw = re.findall(r"[\w']+", target.lower())
    hw = re.findall(r"[\w']+", heard.lower())
    sm = difflib.SequenceMatcher(None, tw, hw)
    words = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        for w in tw[a1:a2]:
            words.append({"word": w, "ok": op == "equal"})
    score = round(100 * sm.ratio(), 1)
    return {"score": score, "words": words, "heard": heard}


SPEAKING_CHALLENGES = [
    {"id": "intro", "level": 1, "prompt": "Introduce yourself in 4 sentences: name, class, favourite subject and a hobby."},
    {"id": "pet", "level": 1, "prompt": "Describe your favourite animal and why you like it."},
    {"id": "day", "level": 1, "prompt": "Tell me about your morning routine, using words like 'first', 'then', 'after that'."},
    {"id": "hero", "level": 2, "prompt": "Talk about someone you admire and what you learnt from them."},
    {"id": "invent", "level": 2, "prompt": "If you could invent a gadget to help your school, what would it do?"},
    {"id": "festival", "level": 2, "prompt": "Describe how your family celebrates a festival."},
    {"id": "debate", "level": 3, "prompt": "Should homework be given every day? Give two reasons for your opinion."},
    {"id": "news", "level": 3, "prompt": "Explain a science fact that surprised you, as if teaching a younger student."},
]
PRONOUNCE_LINES = ["The quick brown fox jumps over the lazy dog.", "She sells sea shells by the sea shore.",
                   "Thirty three thirsty thrushes.", "I would like a glass of water, please.",
                   "Reading every day makes my vocabulary stronger.", "Our school library has thousands of interesting books."]  # fmt: skip
INTERVIEW_QUESTIONS = ["Tell me about yourself.", "What is your greatest strength?", "Describe a time you solved a problem in a team.",
                       "Why do you want to join this club / programme?", "Where do you see yourself in five years?",
                       "What did you learn from a mistake you made?"]  # fmt: skip


# ------------------------------------------------------------------ career lab (guidance, not prediction)
CAREER_QUESTIONS = [
    ("q1", "I enjoy fixing or building things with my hands.", "build"),
    ("q2", "I like solving maths puzzles and number problems.", "think"),
    ("q3", "I love drawing, music, dance or writing stories.", "create"),
    ("q4", "I like helping friends when they are sad or stuck.", "help"),
    ("q5", "I enjoy leading a team or organising events.", "lead"),
    ("q6", "I like keeping things neat, planned and organised.", "organise"),
    ("q7", "I'm curious how the human body and animals work.", "think"),
    ("q8", "I enjoy coding, computers or gadgets.", "build"),
    ("q9", "I like debating and speaking in front of people.", "lead"),
    ("q10", "I enjoy teaching or explaining things to others.", "help"),
    ("q11", "I like designing posters, clothes or spaces.", "create"),
    ("q12", "I enjoy working with data, lists and records.", "organise"),
]
CAREERS = {
    "build": [("Engineer", "Maths + Physics; JEE / state CETs; B.Tech", "🛠️"), ("Software Developer", "Coding clubs, Maths; B.Tech/BCA; build projects", "💻"),
              ("Robotics Technician", "Science + electronics; ITI/Diploma or B.Tech", "🤖")],
    "think": [("Doctor", "Biology + Chemistry; NEET; MBBS", "🩺"), ("Scientist / Researcher", "Science stream; B.Sc → M.Sc → PhD", "🔬"),
              ("Data Analyst", "Maths + Statistics + coding", "📊")],
    "create": [("Designer", "Art + portfolio; NID/NIFT entrance", "🎨"), ("Writer / Journalist", "Languages, reading; BA / Mass Communication", "✍️"),
               ("Architect", "Maths + drawing; NATA; B.Arch", "🏛️")],
    "help": [("Teacher", "Any stream you love; B.Ed", "🍎"), ("Nurse / Physiotherapist", "Biology; B.Sc Nursing / BPT", "💗"),
             ("Psychologist / Counsellor", "Psychology; BA/B.Sc → MA", "🧠")],
    "lead": [("Lawyer", "Any stream; CLAT; 5-year LLB", "⚖️"), ("Civil Services (IAS/IPS)", "Graduation in any subject; UPSC", "🏛"),
             ("Entrepreneur", "Commerce/any; start small projects, learn finance", "🚀")],
    "organise": [("Chartered Accountant", "Commerce + Maths; CA Foundation", "📒"), ("Banker", "Commerce/Maths; bank exams", "🏦"),
                 ("Project Manager", "Any degree + management skills", "📋")],
}
AREA_LABELS = {"build": "Building & Technology", "think": "Science & Investigation", "create": "Arts & Creativity",
               "help": "Helping & Caring", "lead": "Leading & Persuading", "organise": "Organising & Finance"}


def career_score(answers: dict[str, int]) -> tuple[dict, list]:
    totals: dict[str, list[int]] = {k: [] for k in AREA_LABELS}
    for qid, _, area in CAREER_QUESTIONS:
        v = answers.get(qid)
        if isinstance(v, int) and 1 <= v <= 5:
            totals[area].append(v)
    scores = {a: round(100 * (sum(v) / len(v) - 1) / 4) if v else 0 for a, v in totals.items()}
    top = sorted(scores, key=lambda a: -scores[a])[:3]
    sugg = [{"area": a, "label": AREA_LABELS[a], "score": scores[a],
             "careers": [{"name": n, "roadmap": r, "emoji": e} for n, r, e in CAREERS[a]]} for a in top]  # fmt: skip
    return scores, sugg


SCHOLARSHIPS = [  # DEMO entries for the eligibility finder. Real schemes change yearly: always verify on the official portal.
    {"name": "Merit Scholarship (demo)", "min_class": 8, "max_class": 12, "min_marks": 80, "categories": [], "girls_only": False},
    {"name": "Girl Child Education Support (demo)", "min_class": 6, "max_class": 12, "min_marks": 50, "categories": [], "girls_only": True},
    {"name": "SC/ST Pre-Matric Support (demo)", "min_class": 6, "max_class": 10, "min_marks": 0, "categories": ["sc", "st"], "girls_only": False},
    {"name": "OBC/Minority Post-Matric Support (demo)", "min_class": 11, "max_class": 12, "min_marks": 50, "categories": ["obc", "minority"], "girls_only": False},
    {"name": "Science Talent Search (demo)", "min_class": 9, "max_class": 12, "min_marks": 75, "categories": [], "girls_only": False},
    {"name": "Divyang Learner Support (demo)", "min_class": 1, "max_class": 12, "min_marks": 0, "categories": ["disabled"], "girls_only": False},
]
OFFICIAL_PORTAL = "https://scholarships.gov.in"


def scholarship_match(class_n: int, marks: float, category: str, girl: bool) -> list[dict]:
    out = []
    for s in SCHOLARSHIPS:
        ok = s["min_class"] <= class_n <= s["max_class"] and marks >= s["min_marks"]
        ok = ok and (not s["categories"] or category in s["categories"]) and (not s["girls_only"] or girl)
        if ok:
            out.append({"name": s["name"], "why": f"Class {s['min_class']}–{s['max_class']}, marks ≥ {s['min_marks']}%"})
    return out


# ------------------------------------------------------------------ parent leave from a plain message
_TOMORROW = re.compile(r"\b(tomorrow|tmrw|tmr|kal)\b|రేపు|कल|നാളെ|நாளை", re.I)
_TODAY = re.compile(r"\b(today|aaj)\b|ఈరోజు|आज|ഇന്ന്|இன்று", re.I)
_DAYAFTER = re.compile(r"day after tomorrow|parso|ఎల్లుండి|परसों|മറ്റന്നാൾ|நாளை மறுநாள்", re.I)
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _parse_dates(msg: str, today: date) -> tuple[date, date, float]:
    low = msg.lower()
    found: list[date] = []
    for m in re.finditer(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b", low):
        d, mo, y = int(m[1]), int(m[2]), m[3]
        yr = (int(y) + 2000 if len(y) == 2 else int(y)) if y else today.year
        try:
            dt = date(yr, mo, d)
            found.append(dt if y or dt >= today - timedelta(days=1) else date(yr + 1, mo, d))
        except ValueError:
            pass
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", low):
        try:
            dt = date(today.year, _MONTHS[m[2]], int(m[1]))
            found.append(dt if dt >= today - timedelta(days=1) else date(today.year + 1, _MONTHS[m[2]], int(m[1])))
        except ValueError:
            pass
    conf = 0.9 if found else 0.0
    if not found:
        if _DAYAFTER.search(msg):
            found, conf = [today + timedelta(days=2)], 0.85
        elif _TOMORROW.search(msg):
            found, conf = [today + timedelta(days=1)], 0.85
        elif _TODAY.search(msg):
            found, conf = [today], 0.8
        else:
            for i, dn in enumerate(_DAYS):
                if re.search(rf"\b{dn}\b", low):
                    ahead = (i - today.weekday()) % 7 or 7
                    found, conf = [today + timedelta(days=ahead)], 0.75
                    break
    if not found:
        found, conf = [today + timedelta(days=1)], 0.3  # a guess: the teacher/parent must confirm
    start, end = min(found), max(found)
    m = re.search(r"for\s+(\d{1,2})\s+days?", low)
    if m and start == end:
        end = start + timedelta(days=max(1, int(m[1])) - 1)
    return start, end, conf


def parse_leave_message(msg: str, children: list[tuple[int, str]], today: date) -> dict:
    start, end, conf = _parse_dates(msg, today)
    low = msg.lower()
    child = None
    for cid, name in children:
        first = name.split()[0].lower()
        if first and re.search(rf"\b{re.escape(first)}\b", low):
            child = cid
            break
    if child is None and len(children) == 1:
        child = children[0][0]
    m = re.search(r"\b(?:due to|because of|because|as there is|as|for)\s+(?:a\s+|an\s+|the\s+)?(.{3,160})", msg, re.I)
    reason = (m[1] if m else msg).strip().rstrip(".")
    kind = "other"
    if re.search(r"\b(fever|sick|ill|unwell|cold|cough|doctor|hospital|health|stomach|injur\w*|vomit\w*)\b", low):
        kind = "sick"
    elif re.search(r"family|function|wedding|marriage|ceremony|festival|puja|pooja|relative|funeral|travel|village", low):
        kind = "family"
    return {"student_id": child, "from_date": start, "to_date": end, "reason": reason[:300], "leave_type": kind,
            "confidence": conf if child else min(conf, 0.4)}  # fmt: skip


# ------------------------------------------------------------------ general chat in a mode (used by /chitti/ask)
# ------------------------------------------------------------------ friendly small talk (offline, 5 languages)
_ST_PATTERNS: list[tuple[str, str]] = [
    ("how", r"\b(how are (you|u)|how r u|how do you do|what'?s up|wassup|kaise ho|kaisi ho|ela unnav|ela unnaru|sukhamano|eppadi irukk)"),
    ("greet", r"^(hi+|hey+|hello+|hii+|helo|good (morning|afternoon|evening)|namaste|namaskar\w*|vanakkam|namaskaram|"
              r"नमस्ते|नमस्कार|హలో|నమస్తే|నమస్కారం|వందనం|നമസ്കാരം|ഹലോ|வணக்கம்|ஹலோ)(?![a-z0-9])"),
    ("name", r"\b(what('?s| is) your name|who are (you|u)|your name|tum kaun|nuvvu evaru|neeyaru|nee yaar)(?![a-z0-9])"),
    ("can", r"\b(what can you do|how can you help( me)?|what do you do)(?![a-z0-9])"),
    ("thanks", r"\b(thanks?|thank (you|u)|thx|ty|dhanyavaad|dhanyavad|shukriya|dhanyavaadalu|nanni|nandri|"
               r"धन्यवाद|शुक्रिया|ధన్యవాదాలు|നന്ദി|நன்றி)(?![a-z0-9])"),
    ("bye", r"^(bye+|good ?bye|see (you|u)|good night|tata|alvida|ok bye)(?![a-z0-9])"),
    ("joke", r"\b(joke|make me laugh|something funny|chutkula)(?![a-z0-9])"),
    ("love", r"\b(i love (you|u)|you are (my )?(best|good|nice|cool|smart)|good job|well done|awesome)(?![a-z0-9])"),
    ("sad", r"\b(i('?m| am) (sad|bored|tired|upset|lonely|stressed)|i feel (sad|bad|low))(?![a-z0-9])"),
]
_ST_REPLY: dict[str, dict[str, list[str]]] = {
    "greet": {
        "en": ["Hello! I'm CHITTI, your study buddy. What shall we learn today?", "Hi there! Nice to hear from you. Ask me anything!"],
        "hi": ["नमस्ते! मैं चिट्टी हूँ, आपका पढ़ाई का दोस्त। आज क्या सीखें?"],
        "te": ["హలో! నేను చిట్టి, నీ చదువు స్నేహితుడిని. ఈ రోజు ఏమి నేర్చుకుందాం?"],
        "ml": ["ഹലോ! ഞാൻ ചിട്ടി, നിന്റെ പഠന കൂട്ടുകാരൻ. ഇന്ന് എന്ത് പഠിക്കാം?"],
        "ta": ["வணக்கம்! நான் சிட்டி, உன் படிப்பு நண்பன். இன்று என்ன கற்றுக்கொள்ளலாம்?"],
    },
    "how": {
        "en": ["I'm doing great, thank you for asking! How are you? Ready to learn something fun?"],
        "hi": ["मैं बहुत अच्छा हूँ, पूछने के लिए धन्यवाद! आप कैसे हैं?"],
        "te": ["నేను బాగున్నాను, అడిగినందుకు ధన్యవాదాలు! నువ్వు ఎలా ఉన్నావు?"],
        "ml": ["ഞാൻ സുഖമായിരിക്കുന്നു, ചോദിച്ചതിന് നന്ദി! നിനക്ക് സുഖമാണോ?"],
        "ta": ["நான் நன்றாக இருக்கிறேன், கேட்டதற்கு நன்றி! நீ எப்படி இருக்கிறாய்?"],
    },
    "name": {
        "en": ["I'm CHITTI, EduNest's friendly robot. I help you learn, solve doubts, practise English and play brain games."],
        "hi": ["मैं चिट्टी हूँ, एडुनेस्ट का दोस्ताना रोबोट। मैं पढ़ाई, सवाल और अंग्रेज़ी में मदद करता हूँ।"],
        "te": ["నేను చిట్టి, ఎడ్యునెస్ట్ స్నేహపూర్వక రోబో. చదువు, సందేహాలు, ఇంగ్లీష్‌లో సహాయం చేస్తాను."],
        "ml": ["ഞാൻ ചിട്ടി, എഡ്യുനെസ്റ്റിന്റെ കൂട്ടുകാരൻ റോബോട്ട്. പഠനത്തിലും സംശയങ്ങളിലും സഹായിക്കും."],
        "ta": ["நான் சிட்டி, எடுநெஸ்ட்டின் நட்பான ரோபோ. படிப்பு, சந்தேகங்கள், ஆங்கிலத்தில் உதவுவேன்."],
    },
    "can": {
        "en": ["I can explain topics step by step, solve maths, check your English, tell riddles, and search your school notes. Just ask!"],
    },
    "thanks": {
        "en": ["You're welcome! Happy to help anytime.", "Any time! Keep up the great work."],
        "hi": ["आपका स्वागत है! कभी भी पूछिए।"], "te": ["పర్వాలేదు! ఎప్పుడైనా అడుగు."],
        "ml": ["സ്വാഗതം! എപ്പോൾ വേണമെങ്കിലും ചോദിക്കൂ."], "ta": ["பரவாயில்லை! எப்போது வேண்டுமானாலும் கேள்."],
    },
    "bye": {
        "en": ["Bye for now! Great talking with you. See you soon!"],
        "hi": ["फिर मिलेंगे! आपसे बात करके अच्छा लगा।"], "te": ["మళ్ళీ కలుద్దాం! నీతో మాట్లాడటం బాగుంది."],
        "ml": ["വീണ്ടും കാണാം! സംസാരിച്ചതിൽ സന്തോഷം."], "ta": ["மீண்டும் சந்திப்போம்! உன்னுடன் பேசியது மகிழ்ச்சி."],
    },
    "joke": {
        "en": ["Why did the maths book look sad? Because it had too many problems!",
               "Why was the computer cold? It left its Windows open!",
               "What do you call a sleeping dinosaur? A dino-snore!"],
    },
    "love": {"en": ["Aww, thank you! You're a star learner yourself."]},
    "sad": {
        "en": ["I'm sorry you feel that way. Taking a short break, a glass of water, or talking to someone you trust can help. "
               "Want to try a quick fun puzzle together?"],
    },
}


VOICE_STYLE = (" You are talking out loud with the user, like a friendly person on a call. Answer in 2 to 4 short, natural "
               "spoken sentences. No lists, tables, markdown, emojis or links. Ask a short follow-up question when it helps.")


def small_talk(text: str, lang: str = "en") -> str | None:
    """Short friendly replies for greetings, thanks, jokes etc. so CHITTI always answers like a person, even offline."""
    t = text.strip().lower()
    if not t or len(t) > 80:
        return None
    for intent, pat in _ST_PATTERNS:
        m = re.search(pat, t)
        if not m:
            continue
        rest = re.findall(r"\w+", (t[: m.start()] + " " + t[m.end():]).replace("chitti", ""))
        if len(rest) > 4:  # "hi, explain photosynthesis" is a real question, not small talk
            continue
        if True:
            opts = _ST_REPLY[intent].get(lang) or _ST_REPLY[intent]["en"]
            return opts[len(t) % len(opts)]
    return None


def offline_mode_reply(mode: str, text: str, hits: list[Hit], lang: str = "en") -> str:
    chat = small_talk(text, lang)
    if chat and mode != "english":
        return chat
    if mode == "english":
        r = english_check(text)
        lines = [f"✅ Corrected: {r['corrected']}"]
        lines += [f"• '{i['wrong']}' → '{i['right']}': {i['why']}" for i in r["issues"][:6]]
        lines += [f"💡 Instead of '{v['word']}', try '{v['better']}'." for v in r["vocab"]]
        lines += r["tips"][:2]
        return "\n".join(lines)
    if mode in ("doubt_solver", "aptitude"):
        s = solve_offline(text)
        if s:
            return "Here's how to solve it:\n" + "\n".join(f"{i + 1}. {st}" for i, st in enumerate(s["steps"])) + f"\n\n🎯 Answer: {s['answer']}"
    if mode == "puzzle":
        riddles = [("I have keys but open no locks. What am I?", "A keyboard (or a piano)!"),
                   ("What has hands but cannot clap?", "A clock!"), ("The more you take, the more you leave behind. What are they?", "Footsteps!"),
                   ("What gets wetter the more it dries?", "A towel!"), ("I'm tall when I'm young and short when I'm old. What am I?", "A candle!")]  # fmt: skip
        q, a = riddles[len(text) % len(riddles)]
        return f"🧩 Riddle time! {q}\n\nThink for a moment… then tap again for another one.\n\n(Answer: ||{a}||)"
    if mode == "career":
        return ("Open the Career Lab to take the interest quiz. I'll suggest a few career directions with roadmaps. "
                "Remember: these are ideas to explore, not predictions. You can be anything you work towards! 🚀")
    found = kb.find(text)
    s = solve_offline(text)  # a recognisable maths question is answered by the solver in every mode
    if s:
        return "Here's how to solve it:\n" + "\n".join(f"{i + 1}. {st}" for i, st in enumerate(s["steps"])) + f"\n\n🎯 Answer: {s['answer']}"
    if hits:
        return "From your school library:\n\n" + "\n\n".join(f"📘 {h.text[:400]}\n— {h.label}" for h in hits[:2])
    if found:
        t = found[1]
        return f"**{t['title']}**\n\n{t['explain']}\n\n🌟 Example: {t['example']}\n\n" + "\n".join(f"• {p}" for p in t["points"])
    s = solve_offline(text)
    if s:
        return "\n".join(f"{i + 1}. {st}" for i, st in enumerate(s["steps"])) + f"\n\n🎯 Answer: {s['answer']}"
    return ("I'm not sure about that yet. In offline mode I can explain my starter topics (try 'photosynthesis', 'fractions', "
            "'solar system'), solve maths step by step, coach your English, and search your school library. Ask your teacher "
            "to upload notes so I can learn more!")


def mode_ask(mode: str, text: str, lang: str, class_name: str | None, history: list[tuple[str, str]], hits: list[Hit],
             image: tuple[bytes, str] | None = None, voice: bool = False) -> tuple[str, str]:
    """Returns (reply, provider). voice=True asks for short, spoken-style answers (talk mode)."""
    if providers.configured():
        ctx = "\n\n".join(f"[source: {h.label}]\n{h.text}" for h in hits)
        prompt = f"School material:\n{ctx}\n\nMessage: {text}" if ctx else text
        extra = VOICE_STYLE if voice else ""
        try:
            return providers.complete(providers.system_prompt(MODE_PROMPTS.get(mode, "") + extra, lang, level_text(class_name)),
                                      [*history[-8:], ("user", prompt)], image=image), providers.provider_name()  # fmt: skip
        except providers.LLMError:
            pass
    return offline_mode_reply(mode, text, hits, lang), "stub"


def read_file_bytes(rel_path: str, upload_dir: str) -> bytes:
    return (Path(upload_dir) / rel_path).read_bytes()
