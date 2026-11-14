"""Bridge to services/vision (Flask smart-attendance demo). We only CALL it over HTTP; it is never edited.

The vision service is single-session and single-tenant: one global camera session, identified by 'Register Number'
(= our admission_no). To keep schools from seeing each other we (a) remember which school/section started the
session, (b) refuse other callers while it runs, and (c) never pass vision rows through: every row is re-mapped to
the roster of the caller's section in OUR database, so names/ids from anything else are dropped.
"""
import threading
from datetime import date

import httpx
from fastapi import HTTPException, status

from .config import get_settings

_transport: httpx.BaseTransport | None = None  # tests inject httpx.MockTransport here
_lock = threading.Lock()
_owner: dict | None = None  # {"school_id", "section_id", "period", "user_id"}


def _client() -> httpx.Client:
    s = get_settings()
    headers = {"X-Token": s.vision_token} if s.vision_token else {}
    return httpx.Client(base_url=s.vision_url, timeout=s.vision_timeout_seconds, headers=headers, transport=_transport)


def _call(method: str, path: str, **kw) -> dict:
    try:
        with _client() as c:
            r = c.request(method, path, **kw)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Vision service error ({e.response.status_code})")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Smart-attendance service is not reachable")


def reset() -> None:  # tests
    global _owner
    _owner = None


def owner() -> dict | None:
    return _owner


def start(school_id: int, section_id: int, user_id: int, period: int) -> dict:
    global _owner
    with _lock:
        st = _call("GET", "/api/status")
        if st.get("running"):
            if _owner and _owner["school_id"] == school_id and _owner["section_id"] == section_id:
                return st  # idempotent for the same class
            raise HTTPException(status.HTTP_409_CONFLICT, "Another smart-attendance session is already running")
        _call("POST", "/api/start", json={"period": period})
        _owner = {"school_id": school_id, "section_id": section_id, "period": period, "user_id": user_id}
        return _call("GET", "/api/status")


def _require_owner(school_id: int, section_id: int) -> dict:
    if not _owner or _owner["school_id"] != school_id or _owner["section_id"] != section_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No smart-attendance session for this class")
    return _owner


def status_rows(school_id: int, section_id: int) -> tuple[dict, dict]:
    o = _require_owner(school_id, section_id)
    return o, _call("GET", "/api/status")


def stop(school_id: int, section_id: int) -> tuple[dict, list[dict]]:
    """Stop the session and return (owner, present_rows). Falls back to the pre-stop snapshot if the saved file is empty."""
    global _owner
    with _lock:
        o = _require_owner(school_id, section_id)
        snapshot = _call("GET", "/api/status").get("present", [])
        _call("POST", "/api/stop")
        rows: list[dict] = []
        try:
            rec = _call("GET", "/api/records", params={"date": date.today().isoformat(), "period": o["period"]})
            rows = rec.get("present", [])
        except HTTPException:
            pass
        _owner = None
        return o, rows or snapshot
