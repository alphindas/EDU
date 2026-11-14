"""WebSockets: one per-user channel (new DMs, notifications) + live bus location.

Auth: ?token=<access JWT> (browsers can't set headers on WebSocket). Sync routes publish through `hub.send_user`,
which hops onto the event loop thread-safely. In-memory: a single API process. Use Redis pub/sub for several workers."""
import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from ..db import get_db
from ..models import User
from ..security import decode_token

router = APIRouter(tags=["realtime"])


class Hub:
    def __init__(self) -> None:
        self.users: dict[int, set[WebSocket]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def _send(self, uid: int, msg: dict) -> None:
        for ws in list(self.users.get(uid, ())):
            with contextlib.suppress(Exception):
                await ws.send_json(msg)

    def send_user(self, uid: int, msg: dict) -> None:
        if not self.loop or uid not in self.users:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._send(uid, msg), self.loop)
        except RuntimeError:
            pass


hub = Hub()


@contextlib.contextmanager
def _session():
    """Same session factory the HTTP routes use (honours test overrides of get_db)."""
    from ..main import app

    gen = app.dependency_overrides.get(get_db, get_db)()
    try:
        yield next(gen)
    finally:
        gen.close()


def _user_for(token: str | None) -> User | None:
    uid = decode_token(token or "", "access")
    if uid is None:
        return None
    with _session() as db:
        u = db.scalar(select(User).where(User.id == uid))
        return u if u and u.is_active else None


@router.websocket("/ws")
async def user_channel(ws: WebSocket, token: str | None = None):
    user = _user_for(token)
    if not user:
        await ws.close(code=4401)
        return
    hub.loop = hub.loop or asyncio.get_running_loop()
    await ws.accept()
    hub.users.setdefault(user.id, set()).add(ws)
    try:
        await ws.send_json({"type": "hello", "user_id": user.id})
        while True:
            await ws.receive_text()  # pings from the client keep the socket alive
    except WebSocketDisconnect:
        pass
    finally:
        hub.users.get(user.id, set()).discard(ws)


@router.websocket("/ws/bus/{vehicle_id}")
async def bus_channel(ws: WebSocket, vehicle_id: int, token: str | None = None):
    from .transport import live_for

    user = _user_for(token)
    if not user:
        await ws.close(code=4401)
        return
    await ws.accept()
    try:
        while True:
            with _session() as db:
                db.info["school_id"] = user.school_id
                data = live_for(db, user, vehicle_id)
            await ws.send_json({"type": "bus", **data} if data else {"type": "error", "detail": "not allowed"})
            if not data:
                break
            await asyncio.sleep(3)
    except (WebSocketDisconnect, RuntimeError):
        pass
