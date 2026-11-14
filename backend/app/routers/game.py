"""Knowledge Adventure (gamification) + Knowledge Growth (cognitive puzzles) + daily check-in, quests, boss & mystery."""
import random
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import brain, gamify, kb
from ..db import get_db
from ..deps import current_user, require_roles, tenant_id
from ..models import Role, Student, User
from ..models_v2 import BrainAttempt, QuestClaim, ShopPurchase, Streak, StudentPrefs, UserBadge, XpEvent
from .v2util import me_student, target_student

router = APIRouter(tags=["adventure"])
student_only = require_roles(Role.student)


def _profile(db: Session, sid: int, stu: Student, full: bool = True) -> dict:
    xp, coins = gamify.totals(db, stu.id)
    st = db.scalar(select(Streak).where(Streak.student_id == stu.id))
    badges = {b.badge: b.created_at for b in db.scalars(select(UserBadge).where(UserBadge.student_id == stu.id))}
    world_xp = dict(db.execute(select(XpEvent.world, func.sum(XpEvent.xp)).where(XpEvent.student_id == stu.id, XpEvent.world != "")
                               .group_by(XpEvent.world)).all())  # fmt: skip
    worlds = []
    for w, cfg in gamify.WORLDS.items():
        wx = int(world_xp.get(w, 0) or 0)
        stage = max(i for i, t in enumerate(gamify.WORLD_STAGES) if wx >= t) + 1
        nxt = gamify.WORLD_STAGES[stage] if stage < len(gamify.WORLD_STAGES) else None
        worlds.append({"id": w, "emoji": cfg["emoji"], "xp": wx, "stage": stage, "stages": len(gamify.WORLD_STAGES), "next_at": nxt})
    p = gamify.prefs(db, sid, stu.id)
    out = {
        "student_id": stu.id, "name": stu.user.full_name, "xp": xp, "coins": coins, "level": gamify.level_of(xp),
        "streak": {"current": st.current if st else 0, "best": st.best if st else 0, "freezes": st.freezes if st else 1,
                   "today": bool(st and st.last_day == date.today())},
        "badges": [{"id": b, "emoji": e, "earned": b in badges, "at": badges.get(b)} for b, e in gamify.BADGES.items()],
        "worlds": worlds, "team": p.team, "avatar": p.avatar or {}, "leaderboard_opt_in": p.leaderboard_opt_in,
    }  # fmt: skip
    if full:
        today = date.today()
        out["quests"] = gamify.daily_quests(db, stu.id, today)
        out["checked_in"] = bool(db.scalar(select(XpEvent.id).where(XpEvent.student_id == stu.id, XpEvent.kind == "checkin", XpEvent.day == today)))
        out["mystery_done"] = bool(db.scalar(select(XpEvent.id).where(XpEvent.student_id == stu.id, XpEvent.kind == "mystery", XpEvent.day == today)))
        week = today - timedelta(days=6)
        daily = dict(db.execute(select(XpEvent.day, func.sum(XpEvent.xp)).where(XpEvent.student_id == stu.id, XpEvent.day >= week)
                                .group_by(XpEvent.day)).all())  # fmt: skip
        out["week"] = [{"day": (week + timedelta(days=i)).isoformat(), "xp": int(daily.get(week + timedelta(days=i), 0) or 0)} for i in range(7)]
        out["recent"] = [{"kind": e.kind, "xp": e.xp, "coins": e.coins, "day": e.day, "world": e.world}
                         for e in db.scalars(select(XpEvent).where(XpEvent.student_id == stu.id).order_by(XpEvent.id.desc()).limit(8))]
        out["shop"] = [{"id": k, "emoji": e, "cost": c, "owned": False} for k, (e, c) in gamify.SHOP.items()]
        owned = set(db.scalars(select(ShopPurchase.item).where(ShopPurchase.student_id == stu.id)))
        for it in out["shop"]:
            it["owned"] = it["id"] in owned
    return out


@router.get("/game/profile")
def profile(student_id: int | None = None, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = target_student(db, user, sid, student_id)
    out = _profile(db, sid, stu, full=user.role == Role.student.value)
    db.commit()  # prefs row may have been created
    return out


@router.post("/game/checkin")
def checkin(user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    if db.scalar(select(XpEvent.id).where(XpEvent.student_id == stu.id, XpEvent.kind == "checkin", XpEvent.day == date.today())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Already checked in today")
    st = db.scalar(select(Streak).where(Streak.student_id == stu.id))
    bonus = min(20, (st.current if st else 0) * 2)  # streak bonus rewards consistency
    r = gamify.award(db, sid, stu.id, "checkin", 5 + bonus, coins=2)
    db.commit()
    return r


@router.post("/game/quests/{quest_id}/claim")
def claim_quest(quest_id: str, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    today = date.today()
    q = next((x for x in gamify.daily_quests(db, stu.id, today) if x["id"] == quest_id), None)
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not one of today's quests")
    if q["claimed"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already claimed")
    if not q["done"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Quest not finished yet")
    db.add(QuestClaim(school_id=sid, student_id=stu.id, day=today, quest=quest_id))
    r = gamify.award(db, sid, stu.id, "quest", q["xp"], coins=q["coins"], meta={"quest": quest_id})
    db.commit()
    return r


class PrefsIn(BaseModel):
    leaderboard_opt_in: bool | None = None
    avatar: dict | None = None


@router.patch("/game/prefs")
def set_prefs(body: PrefsIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    p = gamify.prefs(db, sid, stu.id)
    if body.leaderboard_opt_in is not None:
        p.leaderboard_opt_in = body.leaderboard_opt_in
    if body.avatar is not None:
        owned = set(db.scalars(select(ShopPurchase.item).where(ShopPurchase.student_id == stu.id)))
        clean = {k: v for k, v in body.avatar.items() if k in ("hat", "color", "pet") and (v in owned or v in ("", None))}
        p.avatar = clean
    db.commit()
    return {"leaderboard_opt_in": p.leaderboard_opt_in, "avatar": p.avatar}


@router.post("/game/shop/{item}/buy")
def buy(item: str, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if item not in gamify.SHOP:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such item")
    stu = me_student(db, user)
    if db.scalar(select(ShopPurchase.id).where(ShopPurchase.student_id == stu.id, ShopPurchase.item == item)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Already owned")
    _, coins = gamify.totals(db, stu.id)
    cost = gamify.SHOP[item][1]
    if coins < cost:
        raise HTTPException(status.HTTP_409_CONFLICT, "Not enough knowledge coins yet")
    db.add(ShopPurchase(school_id=sid, student_id=stu.id, item=item, cost=cost))
    db.commit()
    return {"item": item, "coins_left": coins - cost}


@router.get("/game/leaderboard")
def leaderboard(user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Weekly. Individuals appear ONLY if they opted in; teams (houses) always shown. Ranks effort, not marks."""
    week = date.today() - timedelta(days=6)
    section_id = None
    if user.role == Role.student.value:
        section_id = me_student(db, user).section_id
    rows = db.execute(select(Student, func.coalesce(func.sum(XpEvent.xp), 0)).join(XpEvent, XpEvent.student_id == Student.id)
                      .where(Student.school_id == sid, XpEvent.day >= week, *( [Student.section_id == section_id] if section_id else []))
                      .group_by(Student.id)).all()  # fmt: skip
    prefs = {p.student_id: p for p in db.scalars(select(StudentPrefs).where(StudentPrefs.school_id == sid))}
    teams: dict[str, int] = {t: 0 for t in gamify.TEAMS}
    people = []
    for s, xp in rows:
        p = prefs.get(s.id)
        team = p.team if p and p.team else gamify.TEAMS[s.id % len(gamify.TEAMS)]
        teams[team] = teams.get(team, 0) + int(xp)
        if p and p.leaderboard_opt_in:
            people.append({"student_id": s.id, "name": s.user.full_name.split(" ")[0], "xp": int(xp), "me": s.user_id == user.id})
    people.sort(key=lambda r: -r["xp"])
    return {"people": people[:20], "teams": sorted([{"team": t, "xp": x} for t, x in teams.items()], key=lambda r: -r["xp"]),
            "hidden": len(rows) - len(people)}


# ------------------------------------------------------------------ knowledge growth puzzles
@router.get("/growth/puzzle")
def puzzle(skill: str = Query("logical"), difficulty: int | None = Query(None, ge=1, le=5), user: User = Depends(student_only),
           sid: int = Depends(tenant_id), db: Session = Depends(get_db)):  # fmt: skip
    if skill not in brain.SKILLS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"skill must be one of {', '.join(brain.SKILLS)}")
    stu = me_student(db, user)
    if difficulty is None:
        rows = list(db.scalars(select(BrainAttempt).where(BrainAttempt.student_id == stu.id, BrainAttempt.skill == skill)
                               .order_by(BrainAttempt.id.desc()).limit(10)))  # fmt: skip
        difficulty = brain.next_difficulty(rows)
    return brain.make(skill, difficulty, stu.id)


class AnswerIn(BaseModel):
    token: str = Field(max_length=2000)
    choice: int = Field(ge=0, le=3)
    time_ms: int = Field(0, ge=0, le=3_600_000)


def _check(db: Session, sid: int, stu: Student, body: AnswerIn, tag: str = "") -> tuple[bool, dict]:
    p = brain.verify(body.token, stu.id)
    if tag and p.get("g") != tag:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Puzzle does not belong to this challenge")
    if db.scalar(select(BrainAttempt.id).where(BrainAttempt.nonce == p["n"])):
        raise HTTPException(status.HTTP_409_CONFLICT, "Already answered")
    ok = body.choice == p["a"]
    db.add(BrainAttempt(school_id=sid, student_id=stu.id, skill=p["s"], difficulty=p["d"], correct=ok, time_ms=body.time_ms, nonce=p["n"]))
    return ok, p


@router.post("/growth/answer")
def answer(body: AnswerIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    ok, p = _check(db, sid, stu, body)
    # effort counts: a try earns 1 XP, a correct answer earns more at higher difficulty
    reward = gamify.award(db, sid, stu.id, "brain", (3 + 2 * p["d"]) if ok else 1, coins=1 if ok else 0, world=gamify.skill_world(p["s"]),
                          meta={"skill": p["s"], "d": p["d"], "ok": ok})  # fmt: skip
    db.commit()
    return {"correct": ok, "answer": p["a"], "explanation": p["e"], "reward": reward}


@router.get("/growth/scores")
def scores(student_id: int | None = None, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = target_student(db, user, sid, student_id)
    rows = list(db.scalars(select(BrainAttempt).where(BrainAttempt.student_id == stu.id).order_by(BrainAttempt.id.desc()).limit(400)))
    sc = brain.growth_scores(rows)
    tried = [k for k, v in sc.items() if v["attempts"]]
    overall = round(sum(sc[k]["score"] for k in tried) / len(tried)) if tried else 0
    untried = [k for k in brain.SKILLS if not sc[k]["attempts"]]
    rec = untried[0] if untried else min(tried, key=lambda k: sc[k]["score"])
    weekly: dict[str, list[bool]] = {}
    for r in rows:  # grouped in Python so it works on SQLite and Postgres alike
        y, w, _ = r.created_at.isocalendar()
        weekly.setdefault(f"{y}-W{w:02d}", []).append(r.correct)
    hist = [{"week": k, "accuracy": round(100 * sum(v) / len(v))} for k, v in sorted(weekly.items())][-8:]
    return {"student_id": stu.id, "label": "Learning Growth Score", "overall": overall, "skills": sc, "recommend": rec,
            "emoji": brain.SKILL_EMOJI, "history": hist}


# ------------------------------------------------------------------ boss challenges + mystery quiz
@router.get("/game/boss/{world}")
def boss(world: str, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if world not in gamify.WORLDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such world")
    stu = me_student(db, user)
    xp, _ = gamify.totals(db, stu.id)
    lvl = gamify.level_of(xp)["level"]
    d = min(5, 1 + lvl // 2)
    skills = gamify.WORLDS[world]["skills"]
    done = bool(db.scalar(select(XpEvent.id).where(XpEvent.student_id == stu.id, XpEvent.kind == "boss", XpEvent.day == date.today(),
                                                   XpEvent.world == world)))  # fmt: skip
    return {"world": world, "difficulty": d, "done_today": done,
            "puzzles": [brain.make(skills[i % len(skills)], d, stu.id, tag=f"boss:{world}") for i in range(5)]}


class BossIn(BaseModel):
    answers: list[AnswerIn] = Field(min_length=1, max_length=5)


@router.post("/game/boss/{world}")
def boss_submit(world: str, body: BossIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if world not in gamify.WORLDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such world")
    stu = me_student(db, user)
    results = [_check(db, sid, stu, a, tag=f"boss:{world}") for a in body.answers]
    right = sum(ok for ok, _ in results)
    won = right >= 4
    done = bool(db.scalar(select(XpEvent.id).where(XpEvent.student_id == stu.id, XpEvent.kind == "boss", XpEvent.day == date.today(), XpEvent.world == world)))
    reward = None
    if won and not done:
        reward = gamify.award(db, sid, stu.id, "boss", 60, coins=30, world=world, meta={"right": right})
    elif not done:
        reward = gamify.award(db, sid, stu.id, "brain", 5 + 3 * right, coins=right, world=world, meta={"boss_try": right})
    db.commit()
    return {"right": right, "total": len(results), "won": won, "reward": reward,
            "details": [{"correct": ok, "answer": p["a"], "explanation": p["e"]} for ok, p in results]}


@router.get("/game/mystery")
def mystery(user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    """Today's mystery quiz: 3 surprise questions from the starter topics (same for the whole school each day)."""
    stu = me_student(db, user)
    rnd = random.Random(date.today().toordinal())
    keys = rnd.sample(list(kb.TOPICS), 3)
    qs = [dict(rnd.choice(kb.TOPICS[k]["questions"]), topic=kb.TOPICS[k]["title"]) for k in keys]
    done = bool(db.scalar(select(XpEvent.id).where(XpEvent.student_id == stu.id, XpEvent.kind == "mystery", XpEvent.day == date.today())))
    return {"questions": [{"q": q["q"], "o": q["o"], "topic": q["topic"]} for q in qs], "done": done}


class MysteryIn(BaseModel):
    choices: list[int] = Field(min_length=3, max_length=3)


@router.post("/game/mystery")
def mystery_submit(body: MysteryIn, user: User = Depends(student_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    stu = me_student(db, user)
    if db.scalar(select(XpEvent.id).where(XpEvent.student_id == stu.id, XpEvent.kind == "mystery", XpEvent.day == date.today())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Mystery quiz already opened today. Come back tomorrow!")
    rnd = random.Random(date.today().toordinal())
    keys = rnd.sample(list(kb.TOPICS), 3)
    qs = [rnd.choice(kb.TOPICS[k]["questions"]) for k in keys]
    right = sum(c == q["a"] for c, q in zip(body.choices, qs))
    reward = gamify.award(db, sid, stu.id, "mystery", 5 + 5 * right, coins=4 * right + 2, world="brain", meta={"right": right})
    db.commit()
    return {"right": right, "answers": [q["a"] for q in qs], "explanations": [q["e"] for q in qs], "reward": reward}
