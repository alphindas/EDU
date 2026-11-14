"""English Chitti (communication coach), Career & Innovation Lab, and Personal Growth (beyond academics).

All three are private to the student (parents/teachers see only summary counts, never reflection text). No clinical
claims, no personality labels, no IQ claims; career output is guidance to explore, never a prediction."""
import random
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import chitti, gamify, providers
from ..db import get_db
from ..deps import current_user, require_roles, tenant_id
from ..models import Role, User
from ..models_v2 import CareerResult, EnglishSession, Reflection, XpEvent
from .v2util import burst_limit, class_name_of, log_ai, me_student, require_consent, target_student

router = APIRouter(tags=["coach"])
student_only = require_roles(Role.student)


def _daily_capped(db: Session, stu_id: int, kind: str, cap: int) -> bool:
    n = db.scalar(select(func.count()).select_from(XpEvent).where(XpEvent.student_id == stu_id, XpEvent.kind == kind, XpEvent.day == date.today()))
    return (n or 0) < cap


# ------------------------------------------------------------------ English Chitti
class CheckIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    seconds: float = Field(0, ge=0, le=900)  # speaking duration measured in the browser (0 = typed)
    kind: str = Field("grammar", pattern="^(grammar|speaking|interview)$")
    prompt: str = Field("", max_length=300)
    lang: str = Field("en", pattern="^(en|te|hi|ml|ta)$")  # language for CHITTI's explanations (practice stays English)


@router.get("/english/challenges")
def challenges(user: User = Depends(current_user)):
    return {"speaking": chitti.SPEAKING_CHALLENGES, "pronounce": chitti.PRONOUNCE_LINES, "interview": chitti.INTERVIEW_QUESTIONS}


@router.post("/english/check")
def english_check(body: CheckIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = require_consent(db, user)
    burst_limit(user.id)
    r = chitti.english_check(body.text, body.seconds)
    coach = ""
    if providers.configured():
        try:
            coach = providers.complete(providers.system_prompt(chitti.MODE_PROMPTS["english"], body.lang, level_text_for(db, stu)),
                                       [("user", f"Task: {body.prompt or body.kind}\nStudent said/wrote: {body.text}\nGive warm feedback: "
                                                 "3 fixes with reasons, 2 better words, 1 encouraging tip.")])  # fmt: skip
        except providers.LLMError:
            coach = ""
    db.add(EnglishSession(school_id=sid, student_id=stu.id, kind=body.kind, text=body.text[:3000], words=r["words"], wpm=r["wpm"],
                          fillers=r["fillers"], issues=len(r["issues"]), score=r["score"]))  # fmt: skip
    log_ai(db, sid, user, "/english/check", body.text[:200])
    reward = gamify.award(db, sid, stu.id, "english", 10 if body.kind != "grammar" else 6, coins=2, world="language") \
        if _daily_capped(db, stu.id, "english", 8) else None
    db.commit()
    return {**r, "coach": coach, "reward": reward}


def level_text_for(db: Session, stu) -> str:
    return chitti.level_text(class_name_of(db, stu.class_id))


class PronounceIn(BaseModel):
    target: str = Field(min_length=1, max_length=300)
    heard: str = Field("", max_length=600)  # browser speech-recognition transcript


@router.post("/english/pronounce")
def pronounce(body: PronounceIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = require_consent(db, user)
    r = chitti.pronounce_compare(body.target, body.heard)
    db.add(EnglishSession(school_id=sid, student_id=stu.id, kind="pronounce", text=body.heard[:600], words=len(r["words"]), score=r["score"]))
    reward = gamify.award(db, sid, stu.id, "english", 5, coins=1, world="language") if _daily_capped(db, stu.id, "english", 8) else None
    db.commit()
    return {**r, "reward": reward}


@router.get("/english/progress")
def english_progress(student_id: int | None = None, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Fluency over time. Private: only the student (and, as numbers only, their parent/teacher)."""
    stu = target_student(db, user, sid, student_id)
    rows = list(db.scalars(select(EnglishSession).where(EnglishSession.student_id == stu.id).order_by(EnglishSession.id.desc()).limit(60)))
    own = user.role == Role.student.value
    return {"sessions": [{"id": r.id, "kind": r.kind, "score": r.score, "wpm": r.wpm, "fillers": r.fillers, "issues": r.issues,
                          "words": r.words, "at": r.created_at, "text": r.text if own else None} for r in reversed(rows)],
            "average": round(sum(r.score for r in rows) / len(rows), 1) if rows else 0}  # fmt: skip


# ------------------------------------------------------------------ Career & Innovation Lab
@router.get("/career/questions")
def career_questions(user: User = Depends(current_user)):
    return [{"id": q, "text": t} for q, t, _ in chitti.CAREER_QUESTIONS]


class CareerIn(BaseModel):
    answers: dict[str, int]


@router.post("/career/submit")
def career_submit(body: CareerIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    if len([v for v in body.answers.values() if isinstance(v, int) and 1 <= v <= 5]) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please answer at least 8 questions (1–5)")
    sc, sugg = chitti.career_score(body.answers)
    res = CareerResult(school_id=sid, student_id=stu.id, answers=body.answers, scores=sc, suggestions=sugg)
    db.add(res)
    gamify.award(db, sid, stu.id, "career", 15, coins=5, world="innovation")
    db.commit()
    return {"id": res.id, "scores": sc, "suggestions": sugg, "labels": chitti.AREA_LABELS,
            "note": "These are directions to explore, not predictions. Interests grow and change. Talk to your teachers and family!"}


@router.get("/career/latest")
def career_latest(student_id: int | None = None, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = target_student(db, user, sid, student_id)
    r = db.scalar(select(CareerResult).where(CareerResult.student_id == stu.id).order_by(CareerResult.id.desc()))
    return {"scores": r.scores, "suggestions": r.suggestions, "labels": chitti.AREA_LABELS, "at": r.created_at} if r else None


class ScholarIn(BaseModel):
    marks: float = Field(ge=0, le=100)
    category: str = Field("general", pattern="^(general|obc|sc|st|minority|disabled)$")
    girl: bool = False


@router.post("/career/scholarships")
def scholarships(body: ScholarIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    cname = class_name_of(db, stu.class_id) or "0"
    n = int(cname) if cname.isdigit() else 0
    return {"matches": chitti.scholarship_match(n, body.marks, body.category, body.girl), "official_portal": chitti.OFFICIAL_PORTAL,
            "note": "Demo eligibility rules. Real schemes change every year: always confirm on the official portal."}


LAB = {
    "stem": [
        {"id": "volcano", "emoji": "🌋", "title": "Baking-soda volcano", "time": 30, "skills": ["chemistry", "observation"],
         "steps": ["Mould clay around a bottle", "Add 2 spoons baking soda + a drop of colour", "Pour vinegar and watch!", "Write why bubbles form (CO₂)"]},
        {"id": "rainbow", "emoji": "🌈", "title": "Make a rainbow with a glass of water", "time": 15, "skills": ["light", "refraction"],
         "steps": ["Fill a glass with water", "Place it in sunlight near white paper", "Tilt until colours appear", "Name the 7 colours (VIBGYOR)"]},
        {"id": "seed", "emoji": "🌱", "title": "Seed growth diary", "time": 10, "skills": ["biology", "patience"],
         "steps": ["Put moong seeds on wet cotton", "Keep one in dark, one in light", "Measure daily for a week", "Compare and draw a graph"]},
        {"id": "circuit", "emoji": "💡", "title": "Lemon battery", "time": 40, "skills": ["electricity"],
         "steps": ["Push a copper coin and a zinc nail into a lemon", "Connect 3 lemons in series with wires", "Light a small LED", "Explain where the energy comes from"]},
        {"id": "bridge", "emoji": "🌉", "title": "Paper bridge challenge", "time": 30, "skills": ["engineering", "design"],
         "steps": ["Use only 5 sheets of paper and tape", "Span a 20 cm gap", "Test with coins", "Improve the design and retest"]},
    ],
    "coding": [
        {"id": "c1", "emoji": "🐢", "title": "Predict the output", "level": 1, "code": "x = 3\nfor i in range(3):\n    x = x + 2\nprint(x)",
         "options": ["5", "9", "7", "11"], "answer": 1, "explain": "Loop runs 3 times: 3→5→7→9."},
        {"id": "c2", "emoji": "🔁", "title": "Loop count", "level": 1, "code": "count = 0\nfor n in range(1, 11):\n    if n % 2 == 0:\n        count += 1\nprint(count)",
         "options": ["10", "5", "4", "6"], "answer": 1, "explain": "Even numbers 2,4,6,8,10 → 5."},
        {"id": "c3", "emoji": "🧮", "title": "String magic", "level": 2, "code": "word = 'chitti'\nprint(word.upper()[::-1])",
         "options": ["CHITTI", "ITTIHC", "ittihc", "chitti"], "answer": 1, "explain": "upper() then reverse with [::-1]."},
        {"id": "c4", "emoji": "📦", "title": "List sum", "level": 2, "code": "marks = [7, 8, 10]\nmarks.append(5)\nprint(sum(marks) // len(marks))",
         "options": ["7", "8", "30", "7.5"], "answer": 0, "explain": "30 // 4 = 7 (integer division)."},
        {"id": "c5", "emoji": "🧠", "title": "Function fun", "level": 3, "code": "def f(n):\n    return 1 if n <= 1 else n * f(n - 1)\nprint(f(4))",
         "options": ["10", "24", "16", "4"], "answer": 1, "explain": "4×3×2×1 = 24 (factorial, recursion)."},
    ],
    "projects": [
        {"emoji": "♻️", "title": "Smart waste sorter poster", "idea": "Survey your class's waste for a week and design a sorting plan."},
        {"emoji": "🌦️", "title": "School weather station", "idea": "Record temperature and rain daily; chart trends for a month."},
        {"emoji": "📱", "title": "Kindness app on paper", "idea": "Design screens for an app that helps new students make friends."},
        {"emoji": "💧", "title": "Water saver audit", "idea": "Find leaking taps at home/school and calculate water saved after fixing."},
        {"emoji": "🤖", "title": "CHITTI's cardboard cousin", "idea": "Build a cardboard robot with moving arms using levers and strings."},
    ],
    "courses": [
        {"emoji": "🐍", "title": "Python for beginners", "where": "Ask your computer teacher / free online courses"},
        {"emoji": "🎨", "title": "Digital art & design", "where": "School art club"},
        {"emoji": "🗣️", "title": "Public speaking", "where": "English Chitti speaking challenges + school debate club"},
        {"emoji": "🔭", "title": "Astronomy basics", "where": "Science club night-sky sessions"},
    ],
}


@router.get("/career/lab")
def lab(user: User = Depends(current_user)):
    return LAB


class CodeIn(BaseModel):
    challenge: str
    choice: int = Field(ge=0, le=3)


@router.post("/career/code")
def code_answer(body: CodeIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    c = next((x for x in LAB["coding"] if x["id"] == body.challenge), None)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such challenge")
    stu = me_student(db, user)
    ok = body.choice == c["answer"]
    reward = gamify.award(db, sid, stu.id, "brain", 8 if ok else 1, coins=2 if ok else 0, world="innovation", meta={"code": c["id"]}) \
        if _daily_capped(db, stu.id, "brain", 60) else None
    db.commit()
    return {"correct": ok, "answer": c["answer"], "explain": c["explain"], "reward": reward}


# ------------------------------------------------------------------ Personal Growth
PROMPTS = [
    {"id": "proud", "emoji": "🌟", "kind": "reflection"}, {"id": "learned", "emoji": "💡", "kind": "reflection"},
    {"id": "kind", "emoji": "💖", "kind": "reflection"}, {"id": "tricky", "emoji": "🧗", "kind": "reflection"},
    {"id": "grateful", "emoji": "🙏", "kind": "reflection"}, {"id": "tomorrow", "emoji": "🎯", "kind": "reflection"},
]
MISSIONS = [
    {"id": "compliment", "emoji": "😊", "area": "empathy"}, {"id": "ask_question", "emoji": "🙋", "area": "confidence"},
    {"id": "help_home", "emoji": "🏠", "area": "teamwork"}, {"id": "plan_day", "emoji": "🗓️", "area": "time_management"},
    {"id": "read_15", "emoji": "📖", "area": "healthy_habits"}, {"id": "screen_break", "emoji": "🌳", "area": "healthy_habits"},
    {"id": "thank_teacher", "emoji": "💐", "area": "gratitude"}, {"id": "include_friend", "emoji": "🤝", "area": "leadership"},
    {"id": "new_word", "emoji": "🔤", "area": "communication"}, {"id": "draw_feelings", "emoji": "🎨", "area": "creativity"},
]
SCENARIOS = [
    {"id": "exhibition", "emoji": "🔬", "options": ["talk", "do_all", "tell_teacher", "share_roles"], "best": ["talk", "share_roles"]},
    {"id": "left_out", "emoji": "⚽", "options": ["ignore", "invite", "laugh", "tell_later"], "best": ["invite"]},
    {"id": "exam_stress", "emoji": "📚", "options": ["all_night", "plan_breaks", "give_up", "ask_help"], "best": ["plan_breaks", "ask_help"]},
    {"id": "found_wallet", "emoji": "👛", "options": ["keep", "give_office", "spend", "leave_it"], "best": ["give_office"]},
]


@router.get("/growth/today")
def growth_today(user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    rnd = random.Random(date.today().toordinal() + stu.id)
    done = {(r.kind, r.prompt) for r in db.scalars(select(Reflection).where(Reflection.student_id == stu.id, Reflection.day == date.today()))}
    prompt = rnd.choice(PROMPTS)
    missions = rnd.sample(MISSIONS, 3)
    scen = rnd.choice(SCENARIOS)
    return {"prompt": {**prompt, "done": ("reflection", prompt["id"]) in done},
            "missions": [{**m, "done": ("mission", m["id"]) in done} for m in missions],
            "scenario": {"id": scen["id"], "emoji": scen["emoji"], "options": scen["options"], "done": ("scenario", scen["id"]) in done},
            "note": "Voluntary and private. If something is worrying you, the counselling chat is always open."}


class ReflectIn(BaseModel):
    kind: str = Field("reflection", pattern="^(reflection|mission|scenario)$")
    prompt: str = Field(max_length=80)
    mood: str = Field("", max_length=8)
    text: str = Field("", max_length=2000)


@router.post("/growth/reflections")
def add_reflection(body: ReflectIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    if db.scalar(select(Reflection.id).where(Reflection.student_id == stu.id, Reflection.day == date.today(), Reflection.kind == body.kind,
                                             Reflection.prompt == body.prompt)):  # fmt: skip
        raise HTTPException(status.HTTP_409_CONFLICT, "Already done today")
    db.add(Reflection(school_id=sid, student_id=stu.id, day=date.today(), kind=body.kind, prompt=body.prompt, mood=body.mood, text=body.text.strip()))
    feedback = None
    if body.kind == "scenario":
        sc = next((s for s in SCENARIOS if s["id"] == body.prompt), None)
        feedback = {"kind": body.text in sc["best"]} if sc else None
    reward = gamify.award(db, sid, stu.id, "reflection", 8, coins=3, world="innovation")
    db.commit()
    return {"ok": True, "reward": reward, "feedback": feedback}


@router.get("/growth/reflections")
def my_reflections(user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db),
                   limit: int = Query(30, ge=1, le=100)):  # fmt: skip
    stu = me_student(db, user)
    return [{"id": r.id, "day": r.day, "kind": r.kind, "prompt": r.prompt, "mood": r.mood, "text": r.text}
            for r in db.scalars(select(Reflection).where(Reflection.student_id == stu.id).order_by(Reflection.id.desc()).limit(limit))]
