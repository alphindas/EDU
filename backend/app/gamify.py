"""EduNest Knowledge Adventure: XP, levels, streaks, badges, daily quests, worlds, coins, teams.

Design rules (from the brief): reward effort, consistency, improvement and mastery, not only top scores; leaderboards are
opt-in and team-based by default so nobody is made to feel inferior; coins only buy cosmetic CHITTI accessories."""
import random
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Subject
from .models_v2 import BrainAttempt, QuestClaim, ShopPurchase, Streak, StudentPrefs, UserBadge, XpEvent

WORLDS = {
    "science": {"emoji": "🔬", "subjects": ["science", "physics", "chemistry", "biology", "evs"], "skills": ["critical", "logical", "pattern"]},
    "math": {"emoji": "👑", "subjects": ["mathematics", "maths", "math"], "skills": ["numerical", "pattern", "problem"]},
    "language": {"emoji": "📖", "subjects": ["english", "telugu", "hindi", "malayalam", "tamil", "sanskrit"], "skills": ["verbal", "critical", "memory"]},
    "innovation": {"emoji": "🏝️", "subjects": ["computer", "computers", "social studies", "art"], "skills": ["spatial", "problem", "logical"]},
    "brain": {"emoji": "⚡", "subjects": [], "skills": ["memory", "spatial", "logical", "numerical"]},
}
WORLD_STAGES = [0, 60, 180, 360, 600]  # xp thresholds for the 5 stages of each world

LEVELS = [(0, "curious_seed"), (100, "little_sprout"), (250, "bright_explorer"), (450, "brave_adventurer"),
          (700, "star_scholar"), (1000, "knowledge_knight"), (1400, "wisdom_wizard"), (1900, "galaxy_genius"),
          (2500, "edunest_legend")]  # fmt: skip

BADGES = {  # id -> emoji (names/descriptions live in the i18n files: badge.<id>.name / .desc)
    "first_explorer": "🧭", "knowledge_seeker": "🔎", "math_master": "👑", "word_wizard": "🪄", "puzzle_champion": "🧩",
    "consistency_star": "🌟", "innovation_hero": "💡", "improvement_champion": "📈", "boss_slayer": "🐉",
    "kindness_heart": "💖", "curious_mind": "❓", "early_bird": "🐦",
}
TEAMS = ["sky_hawks", "mint_turtles", "sun_foxes", "lavender_owls"]

QUESTS = [  # id, counts events of kind, target, xp, coins, emoji
    ("quiz1", "quiz", 1, 20, 10, "📝"), ("brain5", "brain", 5, 20, 10, "🧩"), ("flash10", "flashcard", 10, 15, 8, "🃏"),
    ("english1", "english", 1, 15, 8, "🗣️"), ("reflect1", "reflection", 1, 10, 6, "🌈"), ("chitti3", "chitti", 3, 10, 6, "🤖"),
    ("hw1", "homework", 1, 20, 10, "📚"), ("mystery1", "mystery", 1, 15, 10, "🎁"),
]
SHOP = {  # cosmetic accessories for the CHITTI buddy
    "hat_cap": ("🧢", 30), "hat_crown": ("👑", 120), "hat_grad": ("🎓", 80), "hat_party": ("🥳", 40),
    "color_mint": ("🟢", 25), "color_lavender": ("🟣", 25), "color_sun": ("🟡", 25), "color_coral": ("🟠", 25),
    "pet_star": ("⭐", 60), "pet_rocket": ("🚀", 90), "pet_owl": ("🦉", 70), "pet_cat": ("🐱", 70),
}


def subject_world(db: Session, subject_id: int | None) -> str:
    if not subject_id:
        return ""
    name = (db.scalar(select(Subject.name).where(Subject.id == subject_id)) or "").casefold()
    for w, cfg in WORLDS.items():
        if any(s in name for s in cfg["subjects"]):
            return w
    return "innovation"


def skill_world(skill: str) -> str:
    return {"numerical": "math", "pattern": "math", "problem": "math", "verbal": "language", "critical": "science",
            "logical": "brain", "memory": "brain", "spatial": "brain"}.get(skill, "brain")  # fmt: skip


def level_of(xp: int) -> dict:
    idx = max(i for i, (t, _) in enumerate(LEVELS) if xp >= t)
    cur, key = LEVELS[idx]
    nxt = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else None
    return {"level": idx + 1, "key": key, "xp_in_level": xp - cur, "xp_for_next": (nxt - cur) if nxt else None, "next_at": nxt}


def _streak(db: Session, sid: int, student_id: int, today: date) -> Streak:
    st = db.scalar(select(Streak).where(Streak.student_id == student_id))
    if not st:
        st = Streak(school_id=sid, student_id=student_id, current=0, best=0, freezes=1)
        db.add(st)
    if st.last_day == today:
        return st
    if st.last_day == today - timedelta(days=1):
        st.current += 1
    elif st.last_day == today - timedelta(days=2) and st.freezes > 0:  # one missed day forgiven
        st.freezes -= 1
        st.current += 1
    else:
        st.current = 1
    if st.current % 7 == 0:
        st.freezes = min(2, st.freezes + 1)
    st.best = max(st.best, st.current)
    st.last_day = today
    return st


def totals(db: Session, student_id: int) -> tuple[int, int]:
    xp, coins = db.execute(select(func.coalesce(func.sum(XpEvent.xp), 0), func.coalesce(func.sum(XpEvent.coins), 0))
                           .where(XpEvent.student_id == student_id)).one()  # fmt: skip
    spent = db.scalar(select(func.coalesce(func.sum(ShopPurchase.cost), 0)).where(ShopPurchase.student_id == student_id)) or 0
    return int(xp), int(coins) - int(spent)


def _stats(db: Session, student_id: int) -> dict:
    rows = db.execute(select(XpEvent.kind, XpEvent.world, func.count(), func.sum(XpEvent.xp)).where(XpEvent.student_id == student_id)
                      .group_by(XpEvent.kind, XpEvent.world)).all()  # fmt: skip
    by_kind: dict[str, int] = {}
    by_world: dict[str, int] = {}
    for kind, world, n, xp in rows:
        by_kind[kind] = by_kind.get(kind, 0) + n
        if world:
            by_world[world] = by_world.get(world, 0) + int(xp or 0)
    brain_ok = db.scalar(select(func.count()).select_from(BrainAttempt).where(BrainAttempt.student_id == student_id, BrainAttempt.correct.is_(True))) or 0
    st = db.scalar(select(Streak).where(Streak.student_id == student_id))
    pcts = [m.get("pct") for m in db.scalars(select(XpEvent.meta).where(XpEvent.student_id == student_id, XpEvent.kind == "quiz")
                                               .order_by(XpEvent.id)) if isinstance(m, dict) and m.get("pct") is not None]  # fmt: skip
    improved = len(pcts) >= 2 and max(pcts[i] - min(pcts[:i]) for i in range(1, len(pcts))) >= 15
    early = db.scalar(select(func.count()).select_from(XpEvent).where(XpEvent.student_id == student_id, XpEvent.kind == "checkin")) or 0
    return {"kind": by_kind, "world": by_world, "brain_ok": brain_ok, "best": st.best if st else 0, "improved": improved, "checkins": early}


def _earned(s: dict) -> set[str]:
    k, w = s["kind"], s["world"]
    out = set()
    if k:
        out.add("first_explorer")
    if k.get("quiz", 0) + k.get("chitti", 0) >= 10:
        out.add("knowledge_seeker")
    if w.get("math", 0) >= 300:
        out.add("math_master")
    if w.get("language", 0) >= 300 or k.get("english", 0) >= 5:
        out.add("word_wizard")
    if s["brain_ok"] >= 25:
        out.add("puzzle_champion")
    if s["best"] >= 7:
        out.add("consistency_star")
    if k.get("project", 0) >= 1 or w.get("innovation", 0) >= 150:
        out.add("innovation_hero")
    if s["improved"]:
        out.add("improvement_champion")
    if k.get("boss", 0) >= 1:
        out.add("boss_slayer")
    if k.get("reflection", 0) >= 5:
        out.add("kindness_heart")
    if k.get("chitti", 0) >= 20:
        out.add("curious_mind")
    if s["checkins"] >= 5:
        out.add("early_bird")
    return out


def award(db: Session, sid: int, student_id: int, kind: str, xp: int, coins: int = 0, world: str = "", meta: dict | None = None,
          today: date | None = None) -> dict:
    """Add an XP event, update the streak, grant new badges. Caller commits. Returns what changed (for the UI to celebrate)."""
    today = today or date.today()
    before, _ = totals(db, student_id)
    db.add(XpEvent(school_id=sid, student_id=student_id, kind=kind, xp=xp, coins=coins, world=world, day=today, meta=meta or {}))
    st = _streak(db, sid, student_id, today)
    db.flush()
    have = set(db.scalars(select(UserBadge.badge).where(UserBadge.student_id == student_id)))
    new = sorted(_earned(_stats(db, student_id)) - have)
    for b in new:
        db.add(UserBadge(school_id=sid, student_id=student_id, badge=b))
    lv_before, lv_after = level_of(before)["level"], level_of(before + xp)["level"]
    return {"xp": xp, "coins": coins, "new_badges": new, "level_up": lv_after if lv_after > lv_before else None, "streak": st.current}


def daily_quests(db: Session, student_id: int, today: date) -> list[dict]:
    rnd = random.Random(today.toordinal() * 7919 + student_id)
    picks = rnd.sample(QUESTS, 3)
    counts = dict(db.execute(select(XpEvent.kind, func.count()).where(XpEvent.student_id == student_id, XpEvent.day == today)
                             .group_by(XpEvent.kind)).all())  # fmt: skip
    claimed = set(db.scalars(select(QuestClaim.quest).where(QuestClaim.student_id == student_id, QuestClaim.day == today)))
    return [{"id": q, "kind": k, "target": t, "progress": min(t, counts.get(k, 0)), "xp": x, "coins": c, "emoji": e,
             "done": counts.get(k, 0) >= t, "claimed": q in claimed} for q, k, t, x, c, e in picks]  # fmt: skip


def prefs(db: Session, sid: int, student_id: int) -> StudentPrefs:
    p = db.scalar(select(StudentPrefs).where(StudentPrefs.student_id == student_id))
    if not p:
        p = StudentPrefs(school_id=sid, student_id=student_id, team=TEAMS[student_id % len(TEAMS)], avatar={})
        db.add(p)
        db.flush()
    if not p.team:
        p.team = TEAMS[student_id % len(TEAMS)]
    return p


def safe_award(db: Session, sid: int, student_id: int | None, kind: str, xp: int, **kw) -> dict | None:
    """Used by hooks inside other modules: gamification must never break the main action."""
    if not student_id:
        return None
    try:
        return award(db, sid, student_id, kind, xp, **kw)
    except Exception:  # pragma: no cover - defensive; award only adds rows, so a failure here is a bug worth logging
        import logging

        logging.getLogger("edunest.game").exception("award failed")
        return None
