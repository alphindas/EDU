"""Transport: routes with timed stops, vehicles, student stop assignment, live location + ETA.

A GPS device (or the driver's phone) posts positions with the vehicle's device token. When no fix arrived in the last
2 minutes, the position is SIMULATED from the route timetable and clearly flagged `simulated: true` (demo mode)."""
import math
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import child_ids, current_user, require_roles, tenant_id
from ..models import Role, Student, User
from ..models_v2 import StudentTransport, TransportRoute, Vehicle, VehicleLocation
from .structure import get_or_404

router = APIRouter(prefix="/transport", tags=["transport"])
admin_only = require_roles(Role.admin)
FRESH = timedelta(minutes=2)


class StopIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    minute: int = Field(ge=0, le=300)


class RouteIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_time: str = Field("07:30", pattern=r"^\d{2}:\d{2}$")
    stops: list[StopIn] = Field(min_length=2, max_length=40)


class VehicleIn(BaseModel):
    number: str = Field(min_length=1, max_length=20)
    route_id: int | None = None
    driver_name: str = Field("", max_length=100)
    driver_phone: str = Field("", max_length=20)
    capacity: int = Field(40, ge=1, le=120)


class AssignIn(BaseModel):
    student_id: int
    route_id: int
    stop_name: str = Field("", max_length=100)


def _route_out(r: TransportRoute) -> dict:
    return {"id": r.id, "name": r.name, "start_time": r.start_time, "stops": r.stops}


def _veh_out(v: Vehicle, admin: bool = False) -> dict:
    d = {"id": v.id, "number": v.number, "route_id": v.route_id, "driver_name": v.driver_name, "driver_phone": v.driver_phone, "capacity": v.capacity}
    if admin:
        d["device_token"] = v.device_token
    return d


@router.get("/routes")
def routes(user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return [_route_out(r) for r in db.scalars(select(TransportRoute).where(TransportRoute.school_id == sid).order_by(TransportRoute.name))]


@router.post("/routes", status_code=201)
def create_route(body: RouteIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r = TransportRoute(school_id=sid, created_by=user.id, name=body.name, start_time=body.start_time,
                       stops=[s.model_dump() for s in sorted(body.stops, key=lambda s: s.minute)])  # fmt: skip
    db.add(r)
    db.commit()
    return _route_out(r)


@router.put("/routes/{rid}")
def update_route(rid: int, body: RouteIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r = get_or_404(db, TransportRoute, rid, sid)
    r.name, r.start_time, r.stops = body.name, body.start_time, [s.model_dump() for s in sorted(body.stops, key=lambda s: s.minute)]
    db.commit()
    return _route_out(r)


@router.delete("/routes/{rid}", status_code=204)
def delete_route(rid: int, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    r = get_or_404(db, TransportRoute, rid, sid)
    if db.scalar(select(Vehicle.id).where(Vehicle.route_id == r.id)) or db.scalar(select(StudentTransport.id).where(StudentTransport.route_id == r.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Route still has vehicles or students")
    db.delete(r)
    db.commit()


@router.get("/vehicles")
def vehicles(user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    return [_veh_out(v, True) for v in db.scalars(select(Vehicle).where(Vehicle.school_id == sid).order_by(Vehicle.number))]


@router.post("/vehicles", status_code=201)
def create_vehicle(body: VehicleIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    if body.route_id:
        get_or_404(db, TransportRoute, body.route_id, sid)
    v = Vehicle(school_id=sid, created_by=user.id, device_token=secrets.token_hex(16), **body.model_dump())
    db.add(v)
    db.commit()
    return _veh_out(v, True)


@router.delete("/vehicles/{vid}", status_code=204)
def delete_vehicle(vid: int, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    v = get_or_404(db, Vehicle, vid, sid)
    for loc in db.scalars(select(VehicleLocation).where(VehicleLocation.vehicle_id == v.id)):
        db.delete(loc)
    db.delete(v)
    db.commit()


@router.get("/assignments")
def assignments(user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    rows = db.execute(select(StudentTransport, Student).join(Student, Student.id == StudentTransport.student_id).where(StudentTransport.school_id == sid)).all()
    return [{"student_id": s.id, "name": s.user.full_name, "route_id": a.route_id, "stop_name": a.stop_name} for a, s in rows]


@router.put("/assignments")
def assign(body: AssignIn, user: User = Depends(admin_only), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    get_or_404(db, Student, body.student_id, sid)
    r = get_or_404(db, TransportRoute, body.route_id, sid)
    if body.stop_name and body.stop_name not in [s["name"] for s in r.stops]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Stop is not on this route")
    a = db.scalar(select(StudentTransport).where(StudentTransport.student_id == body.student_id))
    if not a:
        a = StudentTransport(school_id=sid, student_id=body.student_id, route_id=r.id)
        db.add(a)
    a.route_id, a.stop_name = r.id, body.stop_name
    db.commit()
    return {"student_id": body.student_id, "route_id": r.id, "stop_name": a.stop_name}


class LocIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    speed_kmh: float = Field(0, ge=0, le=200)


@router.post("/vehicles/{vid}/location", status_code=201)
def post_location(vid: int, body: LocIn, x_device_token: str = Header(""), db: Session = Depends(get_db)):
    """Called by the bus GPS device / driver phone app with its device token (no user login needed)."""
    v = db.scalar(select(Vehicle).where(Vehicle.id == vid))
    if not v or not x_device_token or not secrets.compare_digest(v.device_token, x_device_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad device token")
    db.add(VehicleLocation(school_id=v.school_id, vehicle_id=v.id, lat=body.lat, lng=body.lng, speed_kmh=body.speed_kmh))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ live view
def _dist_km(a: dict, b: dict) -> float:
    r = 6371.0
    la1, la2 = math.radians(a["lat"]), math.radians(b["lat"])
    dla, dlo = la2 - la1, math.radians(b["lng"] - a["lng"])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def simulate(route: TransportRoute, now: datetime) -> dict:
    stops = route.stops
    hh, mm = map(int, route.start_time.split(":"))
    start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    t = (now - start).total_seconds() / 60
    if t < 0:
        return {"lat": stops[0]["lat"], "lng": stops[0]["lng"], "state": "not_started", "t": t, "next_index": 0}
    if t >= stops[-1]["minute"]:
        return {"lat": stops[-1]["lat"], "lng": stops[-1]["lng"], "state": "arrived", "t": t, "next_index": len(stops)}
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        if a["minute"] <= t < b["minute"]:
            f = (t - a["minute"]) / max(1, b["minute"] - a["minute"])
            return {"lat": a["lat"] + (b["lat"] - a["lat"]) * f, "lng": a["lng"] + (b["lng"] - a["lng"]) * f, "state": "on_route",
                    "t": t, "next_index": i + 1, "progress": round(f, 3)}  # fmt: skip
    return {"lat": stops[-1]["lat"], "lng": stops[-1]["lng"], "state": "arrived", "t": t, "next_index": len(stops)}


def _allowed_routes(db: Session, user: User) -> set[int] | None:
    if user.role == Role.admin.value:
        return None
    if user.role == Role.student.value:
        ids = set(db.scalars(select(Student.id).where(Student.user_id == user.id)))
    elif user.role == Role.parent.value:
        ids = child_ids(db, user)
    else:
        return set()
    return set(db.scalars(select(StudentTransport.route_id).where(StudentTransport.student_id.in_(ids or {-1}))))


def live_for(db: Session, user: User, vehicle_id: int) -> dict | None:
    v = db.scalar(select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.school_id == user.school_id))
    if not v or not v.route_id:
        return None
    allowed = _allowed_routes(db, user)
    if allowed is not None and v.route_id not in allowed:
        return None
    route = db.scalar(select(TransportRoute).where(TransportRoute.id == v.route_id))
    now = datetime.now()
    last = db.scalar(select(VehicleLocation).where(VehicleLocation.vehicle_id == v.id).order_by(VehicleLocation.id.desc()))
    sim = simulate(route, now)
    fresh = last and (datetime.now(timezone.utc) - (last.recorded_at if last.recorded_at.tzinfo else last.recorded_at.replace(tzinfo=timezone.utc))) < FRESH
    pos = {"lat": last.lat, "lng": last.lng, "speed_kmh": last.speed_kmh} if fresh else {"lat": sim["lat"], "lng": sim["lng"], "speed_kmh": 25.0 if sim["state"] == "on_route" else 0.0}
    t = sim["t"]
    stops = []
    for i, s in enumerate(route.stops):
        eta = s["minute"] - t
        stops.append({**s, "eta_min": round(eta) if eta > 0 else 0, "passed": eta <= 0})
    if fresh:  # with real GPS: ETA = distance to each remaining stop at ~22 km/h city speed
        for s in stops:
            if not s["passed"]:
                s["eta_min"] = round(_dist_km(pos, s) / 22 * 60)
    return {"vehicle": _veh_out(v), "route": _route_out(route), "position": pos, "state": sim["state"], "simulated": not fresh,
            "stops": stops, "updated_at": (last.recorded_at if fresh else datetime.now(timezone.utc)).isoformat()}  # fmt: skip


@router.get("/my")
def my_transport(user: User = Depends(require_roles(Role.student, Role.parent)), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    ids = set(db.scalars(select(Student.id).where(Student.user_id == user.id))) if user.role == "student" else child_ids(db, user)
    out = []
    for a in db.scalars(select(StudentTransport).where(StudentTransport.student_id.in_(ids or {-1}))):
        s = db.scalar(select(Student).where(Student.id == a.student_id))
        v = db.scalar(select(Vehicle).where(Vehicle.route_id == a.route_id))
        out.append({"student_id": a.student_id, "name": s.user.full_name if s else "", "stop_name": a.stop_name,
                    "live": live_for(db, user, v.id) if v else None, "vehicle_id": v.id if v else None})  # fmt: skip
    return out


@router.get("/live/{vid}")
def live(vid: int, user: User = Depends(current_user), sid: int = Depends(tenant_id), db: Session = Depends(get_db)):
    d = live_for(db, user, vid)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found")
    return d
