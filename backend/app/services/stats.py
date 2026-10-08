"""Statistika: o'qituvchilar, vaqt kesimlari, Excel eksport."""
from collections import defaultdict
from datetime import datetime, timedelta
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.timeutil import local, tz
from ..db.base import utcnow
from ..db.models import LessonSession, Teacher

DONE = ("completed", "cancelled")


def day_range(days: int) -> tuple[datetime, datetime]:
    now = local(utcnow())
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, utcnow() + timedelta(days=1)


def month_start(offset: int = 0) -> datetime:
    now = local(utcnow())
    y, m = now.year, now.month + offset
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return datetime(y, m, 1, tzinfo=tz())


async def fetch_sessions(db, start: datetime, end: datetime, teacher_id: int | None = None):
    q = select(LessonSession).where(LessonSession.started_at >= start, LessonSession.started_at < end,
                                    LessonSession.status.in_(DONE))
    if teacher_id:
        q = q.where(LessonSession.teacher_id == teacher_id)
    q = q.options(selectinload(LessonSession.teacher)).order_by(LessonSession.started_at)
    return (await db.execute(q)).scalars().all()


def _agg(sessions) -> dict:
    return {
        "sessions": len(sessions),
        "blocks": sum(s.blocks_count for s in sessions),
        "planned_minutes": sum(s.planned_minutes for s in sessions),
        "actual_minutes": sum(s.actual_minutes or 0 for s in sessions),
    }


async def summary(db, start, end, teacher_id=None) -> dict:
    return _agg(await fetch_sessions(db, start, end, teacher_id))


async def per_teacher(db, start, end) -> list[dict]:
    sessions = await fetch_sessions(db, start, end)
    by = defaultdict(list)
    for s in sessions:
        by[s.teacher_id].append(s)
    teachers = (await db.execute(select(Teacher).order_by(Teacher.full_name))).scalars().all()
    out = []
    for t in teachers:
        a = _agg(by.get(t.id, []))
        out.append({"teacher_id": t.id, "full_name": t.full_name, "is_active": t.is_active, **a})
    return out


async def timeseries(db, start, end, group: str = "day", teacher_id=None) -> list[dict]:
    sessions = await fetch_sessions(db, start, end, teacher_id)
    buckets: dict[str, list] = defaultdict(list)
    for s in sessions:
        d = local(s.started_at)
        if group == "month":
            key = d.strftime("%Y-%m")
        elif group == "week":
            monday = d - timedelta(days=d.weekday())
            key = monday.strftime("%Y-%m-%d")
        else:
            key = d.strftime("%Y-%m-%d")
        buckets[key].append(s)
    return [{"period": k, **_agg(v)} for k, v in sorted(buckets.items())]


async def export_xlsx(db, start, end) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "O'qituvchilar"
    ws.append(["O'qituvchi", "Darslar", "Bloklar", "Rejalangan (daq)", "Haqiqiy (daq)"])
    for r in await per_teacher(db, start, end):
        ws.append([r["full_name"], r["sessions"], r["blocks"], r["planned_minutes"], r["actual_minutes"]])
    ws2 = wb.create_sheet("Darslar")
    ws2.append(["ID", "O'qituvchi", "Boshlangan", "Bloklar", "Rejalangan (daq)", "Haqiqiy (daq)", "Holat"])
    for s in await fetch_sessions(db, start, end):
        ws2.append([s.id, s.teacher.full_name, local(s.started_at).strftime("%Y-%m-%d %H:%M"),
                    s.blocks_count, s.planned_minutes, s.actual_minutes, s.status])
    for sheet in (ws, ws2):
        for c in sheet[1]:
            c.font = Font(bold=True)
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = 22
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
