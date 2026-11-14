"""Knowledge Growth: adaptive cognitive-skill puzzles (shown as the "Learning Growth Score", never as IQ).

Puzzles are generated on the fly from a nonce and travel as an HMAC-signed token holding the answer, so no puzzle
table is needed and the answer never reaches the browser in clear text. Each nonce can be answered once."""
import base64
import hashlib
import hmac
import json
import random
import secrets
import time

from fastapi import HTTPException, status

from .config import get_settings

SKILLS = ("logical", "numerical", "pattern", "memory", "problem", "spatial", "verbal", "critical")
SKILL_EMOJI = {"logical": "🧩", "numerical": "🔢", "pattern": "🌀", "memory": "🧠", "problem": "🛠️", "spatial": "🧭",
               "verbal": "📚", "critical": "🔍"}  # fmt: skip
TOKEN_TTL = 60 * 30


def _opts(rnd: random.Random, ans, wrong: list) -> tuple[list[str], int]:
    seen, opts = {str(ans)}, [str(ans)]
    for w in wrong:
        if str(w) not in seen and len(opts) < 4:
            seen.add(str(w))
            opts.append(str(w))
    k = 1
    while len(opts) < 4:  # pad numerics
        cand = str(int(ans) + k) if str(ans).lstrip("-").isdigit() else f"{ans}{'!' * k}"
        if cand not in seen:
            seen.add(cand)
            opts.append(cand)
        k += 1
    rnd.shuffle(opts)
    return opts, opts.index(str(ans))


def g_numerical(rnd, d):
    if d == 1:
        a, b = rnd.randint(3, 25), rnd.randint(2, 25)
        return f"{a} + {b} = ?", a + b, [a + b + 1, a + b - 1, a + b + 10], f"{a} + {b} = {a + b}"
    if d == 2:
        a, b = rnd.randint(3, 12), rnd.randint(3, 12)
        return f"{a} × {b} = ?", a * b, [a * b + a, a * b - b, a + b], f"{a} groups of {b} = {a * b}"
    if d == 3:
        a, b, c = rnd.randint(3, 12), rnd.randint(3, 9), rnd.randint(2, 20)
        return f"{a} × {b} − {c} = ?", a * b - c, [a * (b - c), a * b + c, a * b - c + 1], f"Multiply first: {a * b}, then − {c}"
    if d == 4:
        p, n = rnd.choice([10, 20, 25, 50, 75]), rnd.choice([40, 80, 120, 200, 360])
        return f"{p}% of {n} = ?", p * n // 100, [p * n // 50, n - p, p * n // 100 + 10], f"{p}/100 × {n} = {p * n // 100}"
    a, b, c = rnd.randint(12, 40), rnd.randint(2, 6), rnd.randint(2, 9)
    ans = (a * b) // c if (a * b) % c == 0 else a * b + c
    q = f"({a} × {b}) ÷ {c} = ?" if (a * b) % c == 0 else f"{a} × {b} + {c} = ?"
    return q, ans, [ans + c, ans - 2, ans * 2], "Do the bracket / multiplication first"


def g_pattern(rnd, d):
    s = rnd.randint(1, 9)
    if d == 1:
        k = rnd.randint(2, 6)
        seq = [s + k * i for i in range(5)]
        rule = f"add {k} each time"
    elif d == 2:
        k = rnd.choice([2, 3])
        seq = [s * k**i for i in range(5)]
        rule = f"multiply by {k}"
    elif d == 3:
        a, b = rnd.randint(2, 5), rnd.randint(1, 3)
        seq = [s]
        for i in range(4):
            seq.append(seq[-1] + (a if i % 2 == 0 else -b))
        rule = f"+{a}, then −{b}, repeating"
    elif d == 4:
        o = rnd.randint(1, 4)
        seq = [(i + o) ** 2 for i in range(5)]
        rule = "square numbers"
    else:
        a, b = rnd.randint(1, 4), rnd.randint(1, 5)
        seq = [a, b]
        while len(seq) < 5:
            seq.append(seq[-1] + seq[-2])
        rule = "each number is the sum of the two before it"
    ans = seq[-1]
    return f"What comes next? {', '.join(map(str, seq[:-1]))}, ?", ans, [ans + 1, ans - 2, ans + seq[1] - seq[0] + 3], f"Rule: {rule}"


_CATS = {"fruit": ["apple", "mango", "banana", "grape", "papaya", "guava"], "vegetable": ["carrot", "potato", "onion", "brinjal", "cabbage"],
         "animal": ["tiger", "elephant", "rabbit", "deer", "monkey"], "bird": ["parrot", "sparrow", "peacock", "crow", "eagle"],
         "planet": ["Mars", "Venus", "Jupiter", "Saturn", "Mercury"], "instrument": ["veena", "flute", "tabla", "guitar", "violin"]}  # fmt: skip
_NAMES = ["Asha", "Ravi", "Meena", "Arjun", "Zoya", "Kiran", "Neha", "Sam"]


def g_logical(rnd, d):
    if d <= 2:
        c1, c2 = rnd.sample(list(_CATS), 2)
        items = rnd.sample(_CATS[c1], 3)
        odd = rnd.choice(_CATS[c2])
        return f"Odd one out: {', '.join(rnd.sample(items + [odd], 4))}", odd, items, f"The others are all {c1}s; {odd} is a {c2}"
    if d <= 4:
        a, b, c = rnd.sample(_NAMES, 3)
        q = f"{a} is taller than {b}. {b} is taller than {c}. Who is the shortest?"
        return q, c, [a, b, "Can't tell"], f"{a} > {b} > {c}, so {c} is shortest"
    a, b, c, e = rnd.sample(_NAMES, 4)
    q = f"{a} finished before {b}. {c} finished after {b} but before {e}. Who finished last?"
    return q, e, [a, b, c], f"Order: {a}, {b}, {c}, {e}"


_SYMS = "🍎🐱🚗⭐🎈🐟🌙🍩⚽🦋🎵🌻"


def g_memory(rnd, d):
    n = 3 + d
    seq = rnd.sample(_SYMS, n) if d % 2 else [str(rnd.randint(0, 9)) for _ in range(n)]
    pos = rnd.randint(1, n)
    ans = seq[pos - 1]
    others = [x for x in (_SYMS if d % 2 else "0123456789") if x != ans]
    wrong = [x for x in seq if x != ans][:2] + [rnd.choice(others)]
    return f"Which item was in position {pos}?", ans, wrong, f"The sequence was {' '.join(seq)}", {"show": seq, "seconds": 2 + d}


def g_problem(rnd, d):
    if d == 1:
        p, n = rnd.randint(5, 20), rnd.randint(2, 6)
        return f"A pencil costs ₹{p}. How much do {n} pencils cost?", p * n, [p + n, p * n + p, p * (n - 1)], f"{n} × ₹{p} = ₹{p * n}"
    if d == 2:
        have, spent = rnd.randint(50, 200), rnd.randint(10, 45)
        return f"Riya had ₹{have} and spent ₹{spent}. How much is left?", have - spent, [have + spent, have - spent + 10, spent], f"₹{have} − ₹{spent}"
    if d == 3:
        sp, t = rnd.choice([30, 40, 50, 60]), rnd.randint(2, 5)
        return f"A bus goes {sp} km every hour. How far in {t} hours?", sp * t, [sp + t, sp * t + sp, sp * (t - 1)], f"distance = speed × time = {sp * t} km"
    if d == 4:
        total, k = rnd.choice([24, 36, 48, 60]), rnd.choice([3, 4, 6])
        return f"{total} sweets are shared equally among {k} friends. How many each?", total // k, [total // k + 2, k, total - k], f"{total} ÷ {k}"
    start, dur = rnd.randint(1, 10), rnd.choice([45, 75, 90, 105])
    end_m = start * 60 + 30 + dur
    ans = f"{end_m // 60}:{end_m % 60:02d}"
    w = [f"{(end_m + 15) // 60}:{(end_m + 15) % 60:02d}", f"{(end_m - 30) // 60}:{(end_m - 30) % 60:02d}", f"{start + 1}:30"]
    return f"A movie starts at {start}:30 and lasts {dur} minutes. When does it end?", ans, w, f"{start}:30 + {dur} min = {ans}"


_DIRS = ["North", "East", "South", "West"]


def g_spatial(rnd, d):
    face = rnd.randint(0, 3)
    turns = [rnd.choice(["right", "left"] + (["around"] if d >= 3 else [])) for _ in range(1 + d)]
    cur = face
    for t in turns:
        cur = (cur + {"right": 1, "left": -1, "around": 2}[t]) % 4
    ans = _DIRS[cur]
    return (f"You face {_DIRS[face]}. You turn {', then '.join(turns)}. Which way do you face now?", ans,
            [x for x in _DIRS if x != ans], "Right = clockwise quarter turn, left = anticlockwise, around = half turn")


_ANALOGY = [("Bird", "Nest", "Bee", "Hive", ["Honey", "Flower", "Tree"]), ("Hot", "Cold", "Up", "Down", ["Sky", "High", "Over"]),
            ("Doctor", "Hospital", "Teacher", "School", ["Book", "Student", "Class"]), ("Pen", "Write", "Knife", "Cut", ["Sharp", "Kitchen", "Fork"]),
            ("Puppy", "Dog", "Kitten", "Cat", ["Milk", "Mouse", "Pet"]), ("Eye", "See", "Ear", "Hear", ["Sound", "Head", "Loud"]),
            ("Water", "Thirst", "Food", "Hunger", ["Plate", "Eat", "Rice"]), ("Author", "Book", "Painter", "Painting", ["Brush", "Colour", "Wall"])]
_SYN = [("happy", "joyful", ["angry", "tired", "slow"]), ("big", "huge", ["tiny", "light", "short"]), ("brave", "courageous", ["shy", "weak", "lazy"]),
        ("quick", "rapid", ["late", "calm", "quiet"]), ("ancient", "very old", ["modern", "new", "young"]), ("generous", "giving", ["greedy", "proud", "rude"])]  # fmt: skip


def g_verbal(rnd, d):
    if d <= 2:
        w, ans, wrong = rnd.choice(_SYN)
        return f"Which word means the same as '{w}'?", ans, wrong, f"'{w}' and '{ans}' are synonyms"
    a, b, c, ans, wrong = rnd.choice(_ANALOGY)
    return f"{a} is to {b} as {c} is to ___", ans, wrong, f"Same relationship: {a}→{b}, {c}→{ans}"


_FACT_OP = [("Water boils at 100 °C at sea level.", "Fact"), ("Mangoes are the tastiest fruit.", "Opinion"),
            ("India has 28 states.", "Fact"), ("Cricket is more fun than football.", "Opinion"),
            ("The Sun rises in the east.", "Fact"), ("Maths homework is boring.", "Opinion"),
            ("A week has seven days.", "Fact"), ("Blue is the most beautiful colour.", "Opinion")]
_CONC = [("All roses are flowers. Some flowers fade quickly.", "Some roses may fade quickly", ["All roses fade quickly", "No roses fade", "Roses are not flowers"]),
         ("It rained, and the ground is wet. Puddles formed near the gate.", "Rain likely caused the puddles",
          ["The gate is broken", "It will rain tomorrow", "Someone spilled milk"]),
         ("Every student who practised daily improved. Ravi practised daily.", "Ravi improved", ["Ravi did not improve", "Ravi is a teacher", "Nobody improved"])]


def g_critical(rnd, d):
    if d <= 2:
        s, ans = rnd.choice(_FACT_OP)
        return f"Fact or opinion? “{s}”", ans, ["Fact" if ans == "Opinion" else "Opinion", "Both", "Neither"], \
            "A fact can be checked; an opinion is what someone feels"
    p, ans, wrong = rnd.choice(_CONC)
    return f"{p} Which conclusion is best supported?", ans, wrong, "Pick only what the statements actually support"


GEN = {"logical": g_logical, "numerical": g_numerical, "pattern": g_pattern, "memory": g_memory, "problem": g_problem,
       "spatial": g_spatial, "verbal": g_verbal, "critical": g_critical}


def _sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(get_settings().secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def verify(token: str, student_id: int) -> dict:
    try:
        raw, sig = token.rsplit(".", 1)
        good = hmac.new(get_settings().secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, good):
            raise ValueError
        p = json.loads(base64.urlsafe_b64decode(raw))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid puzzle token") from None
    if p.get("u") != student_id or time.time() - p.get("t", 0) > TOKEN_TTL:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Puzzle expired")
    return p


def make(skill: str, difficulty: int, student_id: int, tag: str = "") -> dict:
    d = max(1, min(5, difficulty))
    nonce = secrets.token_hex(8)
    rnd = random.Random(nonce)
    res = GEN[skill](rnd, d)
    q, ans, wrong, explain = res[:4]
    extra = res[4] if len(res) > 4 else {}
    opts, idx = _opts(rnd, ans, wrong)
    token = _sign({"s": skill, "d": d, "a": idx, "n": nonce, "u": student_id, "t": int(time.time()), "e": explain, "g": tag})
    return {"skill": skill, "emoji": SKILL_EMOJI[skill], "difficulty": d, "question": q, "options": opts, "token": token, **extra}


def growth_scores(attempts: list) -> dict:
    """attempts: rows with skill, difficulty, correct (newest first). Score 0..100 per skill + trend."""
    out = {}
    for sk in SKILLS:
        rows = [a for a in attempts if a.skill == sk][:30]
        if not rows:
            out[sk] = {"score": 0, "attempts": 0, "accuracy": 0, "level": 1, "trend": 0}
            continue
        pts = sum(a.difficulty for a in rows if a.correct)
        score = round(100 * pts / (5 * len(rows)) * 0.6 + 100 * sum(a.correct for a in rows) / len(rows) * 0.4)
        recent, older = rows[:10], rows[10:20]
        acc = lambda xs: sum(x.correct for x in xs) / len(xs) if xs else 0  # noqa: E731
        trend = round(100 * (acc(recent) - acc(older))) if older else 0
        out[sk] = {"score": min(100, score), "attempts": len(rows), "accuracy": round(100 * acc(rows)),
                   "level": next_difficulty(rows), "trend": trend}  # fmt: skip
    return out


def next_difficulty(rows: list) -> int:
    """Adaptive: start at the last difficulty; 4+/5 right at it -> up, <=1/5 -> down."""
    if not rows:
        return 1
    cur = rows[0].difficulty
    same = [r for r in rows if r.difficulty == cur][:5]
    right = sum(r.correct for r in same)
    if len(same) >= 3 and right >= len(same) - 1 and right >= 3:
        return min(5, cur + 1)
    if len(same) >= 3 and right <= 1:
        return max(1, cur - 1)
    return cur
