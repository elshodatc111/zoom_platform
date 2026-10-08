"""Fon vazifalar: akkaunt sog'lig'ini tekshirish va oylik hisobot."""
import asyncio
import logging

from sqlalchemy import select

from ..core.timeutil import local
from ..db.base import session_factory, utcnow
from ..db.models import AppSetting, ZoomAccount
from . import stats

log = logging.getLogger("maintenance")


async def health_loop(zoom, notifier, interval: int = 600):
    """Xato holatidagi akkauntlarni har 10 daqiqada qayta tekshiradi."""
    while True:
        await asyncio.sleep(interval)
        try:
            async with session_factory()() as db:
                bad = (await db.execute(select(ZoomAccount).where(
                    ZoomAccount.is_active.is_(True), ZoomAccount.status == "error"))).scalars().all()
                for a in bad:
                    zoom.invalidate(a.id)
                    try:
                        await zoom.test(a)
                        a.status, a.last_error = "ok", None
                        await notifier.admin_alert(f"✅ Zoom akkaunt '{a.name}' qayta ishlayapti")
                    except Exception as e:
                        a.last_error = str(e)[:500]
                    a.last_checked_at = utcnow()
                await db.commit()
        except Exception:
            log.exception("health_loop")


async def monthly_report_loop(notifier):
    """Har oyning 1-kuni 09:00 dan keyin o'tgan oy hisobotini adminlarga yuboradi."""
    while True:
        await asyncio.sleep(1800)
        try:
            now = local(utcnow())
            if now.day != 1 or now.hour < 9:
                continue
            prev = stats.month_start(-1)
            tag = prev.strftime("%Y-%m")
            async with session_factory()() as db:
                st = await db.get(AppSetting, "last_monthly_report")
                if st and st.value == tag:
                    continue
                rows = await stats.per_teacher(db, prev, stats.month_start())
                if st:
                    st.value = tag
                else:
                    db.add(AppSetting(key="last_monthly_report", value=tag))
                await db.commit()
            rows = [r for r in rows if r["sessions"]]
            lines = [f"📅 Oylik hisobot: {tag}"]
            total = 0
            for r in sorted(rows, key=lambda x: -x["actual_minutes"]):
                total += r["actual_minutes"]
                lines.append(f"• {r['full_name']}: {r['sessions']} dars, {r['actual_minutes']} daq")
            lines.append(f"Jami: {total} daqiqa ({total / 60:.1f} soat)")
            await notifier.admin_alert("\n".join(lines))
        except Exception:
            log.exception("monthly_report_loop")
