from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from .config import get_settings

ALGO = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode()[:72], bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)).decode()


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode()[:72], hashed.encode())
    except ValueError:
        return False


def _make(user_id: int, kind: str, minutes: int) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "typ": kind, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, s.secret_key, algorithm=ALGO)


def create_access_token(user_id: int) -> str:
    return _make(user_id, "access", get_settings().access_token_minutes)


def create_refresh_token(user_id: int) -> str:
    return _make(user_id, "refresh", get_settings().refresh_token_days * 24 * 60)


def decode_token(token: str, expected: str) -> int | None:
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=[ALGO])
    except JWTError:
        return None
    if data.get("typ") != expected:
        return None
    try:
        return int(data["sub"])
    except (KeyError, ValueError):
        return None
