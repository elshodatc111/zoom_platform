from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import Response as RawResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import get_settings
from ..core.security import (create_token, encrypt, hash_password, login_limiter, verify_password)
from ..db.base import get_db, utcnow
from ..db.models import (ACTIVE_BLOCK_STATES, Admin, AuditLog, LessonBlock, LessonSession, Teacher, ZoomAccount)
from ..services import stats
from .deps import COOKIE, audit, current_admin

router = APIRouter(prefix="/api")
protected = APIRouter(dependencies=[Depends(current_admin)])


# ============================================================ AUTH
class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(data: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    key = f"{request.client.host if request.client else '?'}:{data.username.lower()}"
    if login_limiter.blocked(key):
        raise HTTPException(429, "Juda ko'p urinish. 15 daqiqadan so'ng qayta urinib ko'ring.")
    admin = (await db.execute(select(Admin).where(Admin.username == data.username))).scalar_one_or_none()
    if not admin or not admin.is_active or not verify_password(data.password, admin.password_hash):
        login_limiter.fail(key)
        raise HTTPException(401, "Login yoki parol noto'g'ri")
    login_limiter.reset(key)
    s = get_settings()
    response.set_cookie(COOKIE, create_token(admin.id), httponly=True, samesite="lax",
                        secure=s.cookie_secure, max_age=s.jwt_hours * 3600, path="/")
    await audit(db, admin, "login")
    await db.commit()
    return {"id": admin.id, "username": admin.username}


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@protected.get("/auth/me")
async def me(admin: Admin = Depends(current_admin)):
    return {"id": admin.id, "username": admin.username}


class PasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


@protected.post("/auth/change-password")
async def change_password(data: PasswordIn, admin: Admin = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    if not verify_password(data.old_password, admin.password_hash):
        raise HTTPException(400, "Eski parol noto'g'ri")
    admin.password_hash = hash_password(data.new_password)
    await audit(db, admin, "password.change")
    await db.commit()
    return {"ok": True}


# ============================================================ ADMINLAR
class AdminIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)


class AdminPatch(BaseModel):
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


@protected.get("/admins")
async def list_admins(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Admin).order_by(Admin.id))).scalars().all()
    return [{"id": a.id, "username": a.username, "is_active": a.is_active, "created_at": a.created_at} for a in rows]


@protected.post("/admins")
async def create_admin(data: AdminIn, me: Admin = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    db.add(Admin(username=data.username, password_hash=hash_password(data.password)))
    await audit(db, me, "admin.create", data.username)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(409, "Bunday login mavjud")
    return {"ok": True}


@protected.patch("/admins/{admin_id}")
async def patch_admin(admin_id: int, data: AdminPatch, me: Admin = Depends(current_admin),
                      db: AsyncSession = Depends(get_db)):
    a = await db.get(Admin, admin_id)
    if not a:
        raise HTTPException(404)
    if data.is_active is not None:
        if a.id == me.id and not data.is_active:
            raise HTTPException(400, "O'zingizni o'chira olmaysiz")
        a.is_active = data.is_active
    if data.password:
        a.password_hash = hash_password(data.password)
    await audit(db, me, "admin.update", a.username)
    await db.commit()
    return {"ok": True}


# ============================================================ O'QITUVCHILAR
class TeacherIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=128)
    telegram_id: int | None = None
    tg_username: str | None = None
    phone: str | None = None
    note: str | None = None
    is_active: bool = True


class TeacherPatch(BaseModel):
    full_name: str | None = None
    telegram_id: int | None = None
    tg_username: str | None = None
    phone: str | None = None
    note: str | None = None
    is_active: bool | None = None


def _clean_username(v: str | None) -> str | None:
    v = (v or "").strip().lstrip("@")
    return v or None


def teacher_dict(t: Teacher, extra: dict | None = None) -> dict:
    d = {"id": t.id, "full_name": t.full_name, "telegram_id": t.telegram_id, "tg_username": t.tg_username,
         "phone": t.phone, "note": t.note, "is_active": t.is_active, "created_at": t.created_at}
    d.update(extra or {})
    return d


@protected.get("/teachers")
async def list_teachers(db: AsyncSession = Depends(get_db)):
    ts = (await db.execute(select(Teacher).order_by(Teacher.full_name))).scalars().all()
    active = {r[0] for r in (await db.execute(
        select(LessonSession.teacher_id).where(LessonSession.status == "active"))).all()}
    month = {r["teacher_id"]: r for r in await stats.per_teacher(db, stats.month_start(), utcnow() + timedelta(days=1))}
    return [teacher_dict(t, {"in_lesson": t.id in active,
                             "month_sessions": month.get(t.id, {}).get("sessions", 0),
                             "month_minutes": month.get(t.id, {}).get("actual_minutes", 0)}) for t in ts]


@protected.post("/teachers")
async def create_teacher(data: TeacherIn, me: Admin = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    uname = _clean_username(data.tg_username)
    if not data.telegram_id and not uname:
        raise HTTPException(400, "Telegram ID yoki @username kiriting")
    t = Teacher(full_name=data.full_name.strip(), telegram_id=data.telegram_id, tg_username=uname,
                phone=data.phone, note=data.note, is_active=data.is_active)
    db.add(t)
    await audit(db, me, "teacher.create", t.full_name)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(409, "Bu Telegram ID yoki username allaqachon ro'yxatda")
    return teacher_dict(t)


@protected.patch("/teachers/{tid}")
async def patch_teacher(tid: int, data: TeacherPatch, me: Admin = Depends(current_admin),
                        db: AsyncSession = Depends(get_db)):
    t = await db.get(Teacher, tid)
    if not t:
        raise HTTPException(404)
    fields = data.model_dump(exclude_unset=True)
    if "tg_username" in fields:
        fields["tg_username"] = _clean_username(fields["tg_username"])
    for k, v in fields.items():
        setattr(t, k, v)
    await audit(db, me, "teacher.update", t.full_name)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(409, "Bu Telegram ID yoki username allaqachon ro'yxatda")
    return teacher_dict(t)


@protected.delete("/teachers/{tid}")
async def delete_teacher(tid: int, me: Admin = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    t = await db.get(Teacher, tid)
    if not t:
        raise HTTPException(404)
    has = (await db.execute(select(func.count()).select_from(LessonSession)
                            .where(LessonSession.teacher_id == tid))).scalar_one()
    if has:
        t.is_active = False  # statistika saqlanishi uchun faqat nofaol qilinadi
        msg = "O'qituvchi nofaol qilindi (darslar tarixi saqlanadi)"
    else:
        await db.delete(t)
        msg = "O'qituvchi o'chirildi"
    await audit(db, me, "teacher.delete", t.full_name)
    await db.commit()
    return {"ok": True, "message": msg}


# ============================================================ ZOOM AKKAUNTLAR
class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    email: str
    zoom_account_id: str
    client_id: str
    client_secret: str


class AccountPatch(BaseModel):
    name: str | None = None
    email: str | None = None
    zoom_account_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    is_active: bool | None = None


def account_dict(a: ZoomAccount, busy: bool = False) -> dict:
    return {"id": a.id, "name": a.name, "email": a.email, "zoom_account_id": a.zoom_account_id,
            "client_id": a.client_id, "is_active": a.is_active, "status": a.status, "last_error": a.last_error,
            "last_checked_at": a.last_checked_at, "busy": busy}


@protected.get("/accounts")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    now = utcnow()
    accs = (await db.execute(select(ZoomAccount).order_by(ZoomAccount.name))).scalars().all()
    busy = {r[0] for r in (await db.execute(select(LessonBlock.account_id).where(
        LessonBlock.status.in_(ACTIVE_BLOCK_STATES), LessonBlock.account_id.is_not(None),
        LessonBlock.create_at <= now + timedelta(minutes=3), LessonBlock.planned_end > now))).all()}
    return [account_dict(a, a.id in busy) for a in accs]


@protected.post("/accounts")
async def create_account(data: AccountIn, request: Request, me: Admin = Depends(current_admin),
                         db: AsyncSession = Depends(get_db)):
    a = ZoomAccount(name=data.name.strip(), email=data.email.strip(), zoom_account_id=data.zoom_account_id.strip(),
                    client_id=data.client_id.strip(), client_secret_enc=encrypt(data.client_secret.strip()))
    db.add(a)
    await audit(db, me, "account.create", a.name)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(409, "Bunday nomli akkaunt mavjud")
    return account_dict(a)


@protected.patch("/accounts/{aid}")
async def patch_account(aid: int, data: AccountPatch, me: Admin = Depends(current_admin),
                        db: AsyncSession = Depends(get_db)):
    a = await db.get(ZoomAccount, aid)
    if not a:
        raise HTTPException(404)
    f = data.model_dump(exclude_unset=True)
    secret = f.pop("client_secret", None)
    for k, v in f.items():
        setattr(a, k, v.strip() if isinstance(v, str) else v)
    if secret:
        a.client_secret_enc = encrypt(secret.strip())
    if any(k in f for k in ("zoom_account_id", "client_id", "email")) or secret:
        a.status = "unknown"
    await audit(db, me, "account.update", a.name)
    try:
        await db.commit()
    except IntegrityError:
        raise HTTPException(409, "Bunday nomli akkaunt mavjud")
    return account_dict(a)


@protected.delete("/accounts/{aid}")
async def delete_account(aid: int, me: Admin = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    a = await db.get(ZoomAccount, aid)
    if not a:
        raise HTTPException(404)
    used = (await db.execute(select(func.count()).select_from(LessonBlock)
                             .where(LessonBlock.account_id == aid))).scalar_one()
    if used:
        a.is_active = False
        msg = "Akkaunt tarixda ishlatilgan, shuning uchun faqat o'chirib qo'yildi (nofaol)"
    else:
        await db.delete(a)
        msg = "Akkaunt o'chirildi"
    await audit(db, me, "account.delete", a.name)
    await db.commit()
    return {"ok": True, "message": msg}


@protected.post("/accounts/{aid}/test")
async def test_account(aid: int, request: Request, db: AsyncSession = Depends(get_db)):
    a = await db.get(ZoomAccount, aid)
    if not a:
        raise HTTPException(404)
    zoom = request.app.state.zoom
    zoom.invalidate(a.id)
    try:
        info = await zoom.test(a)
        a.status, a.last_error = "ok", None
        ok, msg = True, f"Ulandi: {info.get('email')}"
    except Exception as e:
        a.status, a.last_error = "error", str(e)[:500]
        ok, msg = False, str(e)
    a.last_checked_at = utcnow()
    await db.commit()
    return {"ok": ok, "message": msg}


# ============================================================ DARSLAR
def block_dict(b: LessonBlock) -> dict:
    return {"id": b.id, "idx": b.idx, "status": b.status, "account": b.account.name if b.account else None,
            "planned_start": b.planned_start, "planned_end": b.planned_end, "create_at": b.create_at,
            "created_real_at": b.created_real_at, "meeting_id": b.meeting_id, "join_url": b.join_url,
            "error": b.error, "attempts": b.attempts}


def session_dict(s: LessonSession, with_blocks: bool = False) -> dict:
    d = {"id": s.id, "teacher_id": s.teacher_id, "teacher": s.teacher.full_name, "status": s.status,
         "blocks_count": s.blocks_count, "block_minutes": s.block_minutes, "planned_minutes": s.planned_minutes,
         "actual_minutes": s.actual_minutes, "started_at": s.started_at, "ended_at": s.ended_at,
         "stop_reason": s.stop_reason}
    if with_blocks:
        d["blocks"] = [block_dict(b) for b in s.blocks]
    return d


@protected.get("/sessions")
async def list_sessions(status: str | None = None, teacher_id: int | None = None,
                        date_from: datetime | None = None, date_to: datetime | None = None,
                        page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=200),
                        db: AsyncSession = Depends(get_db)):
    q = select(LessonSession)
    if status:
        q = q.where(LessonSession.status == status)
    if teacher_id:
        q = q.where(LessonSession.teacher_id == teacher_id)
    if date_from:
        q = q.where(LessonSession.started_at >= date_from)
    if date_to:
        q = q.where(LessonSession.started_at < date_to)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.options(selectinload(LessonSession.teacher), selectinload(LessonSession.blocks)
                  .selectinload(LessonBlock.account)).order_by(LessonSession.started_at.desc()) \
        .offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    return {"total": total, "items": [session_dict(s, True) for s in rows]}


@protected.post("/sessions/{sid}/stop")
async def admin_stop(sid: int, request: Request, me: Admin = Depends(current_admin),
                     db: AsyncSession = Depends(get_db)):
    ok = await request.app.state.engine.stop_session(sid, actor=f"admin:{me.username}")
    if not ok:
        raise HTTPException(400, "Dars faol emas")
    return {"ok": True}


# ============================================================ DASHBOARD & STATISTIKA
@protected.get("/dashboard")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    active = (await db.execute(select(LessonSession).where(LessonSession.status == "active").options(
        selectinload(LessonSession.teacher), selectinload(LessonSession.blocks).selectinload(LessonBlock.account))
        .order_by(LessonSession.started_at))).scalars().all()
    cap = await request.app.state.engine.capacity()
    today = await stats.summary(db, *stats.day_range(1))
    month = await stats.summary(db, stats.month_start(), utcnow() + timedelta(days=1))
    teachers = (await db.execute(select(func.count()).select_from(Teacher).where(Teacher.is_active.is_(True)))).scalar_one()
    return {"active_sessions": [session_dict(s, True) for s in active], "capacity": cap, "today": today,
            "month": month, "teachers": teachers,
            "bot_running": request.app.state.bot.bot is not None}


def _range(date_from: datetime | None, date_to: datetime | None, days: int = 30):
    if date_from and date_to:
        return date_from, date_to
    s, e = stats.day_range(days)
    return date_from or s, date_to or e


@protected.get("/stats/teachers")
async def stats_teachers(date_from: datetime | None = None, date_to: datetime | None = None,
                         db: AsyncSession = Depends(get_db)):
    s, e = _range(date_from, date_to)
    return await stats.per_teacher(db, s, e)


@protected.get("/stats/timeseries")
async def stats_series(group: str = Query("day", pattern="^(day|week|month)$"), teacher_id: int | None = None,
                       date_from: datetime | None = None, date_to: datetime | None = None,
                       db: AsyncSession = Depends(get_db)):
    s, e = _range(date_from, date_to, 365 if group == "month" else 30)
    return await stats.timeseries(db, s, e, group, teacher_id)


@protected.get("/stats/export")
async def stats_export(date_from: datetime | None = None, date_to: datetime | None = None,
                       db: AsyncSession = Depends(get_db)):
    s, e = _range(date_from, date_to)
    data = await stats.export_xlsx(db, s, e)
    return RawResponse(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       headers={"Content-Disposition": 'attachment; filename="statistika.xlsx"'})


@protected.get("/audit")
async def audit_logs(page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
                     db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count()).select_from(AuditLog))).scalar_one()
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.id.desc())
                             .offset((page - 1) * size).limit(size))).scalars().all()
    return {"total": total, "items": [{"id": r.id, "created_at": r.created_at, "actor": r.actor,
                                       "action": r.action, "detail": r.detail} for r in rows]}


router.include_router(protected)
