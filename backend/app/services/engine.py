"""Dars dvigateli: akkaunt rezervatsiyasi, bloklarni vaqtida yaratish, yakunlash."""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from ..core.config import get_settings
from ..db.base import session_factory, utcnow
from ..db.models import (
    ACTIVE_BLOCK_STATES,
    AuditLog,
    LessonBlock,
    LessonSession,
    Teacher,
    ZoomAccount,
)
from .zoom_client import ZoomError

log = logging.getLogger("engine")


class Notifier:
    """Bot shu sinfni to'ldiradi. Dvigatel Telegram'dan mustaqil."""

    async def block_ready(self, session: LessonSession, teacher: Teacher, block: LessonBlock) -> None: ...
    async def session_finished(self, session: LessonSession, teacher: Teacher) -> None: ...
    async def teacher_error(self, session: LessonSession, teacher: Teacher, text: str) -> None: ...
    async def admin_alert(self, text: str) -> None: ...


def block_times(started_at: datetime, idx: int, block_minutes: int, lead_seconds: int):
    planned_start = started_at + timedelta(minutes=(idx - 1) * block_minutes)
    planned_end = started_at + timedelta(minutes=idx * block_minutes)
    create_at = started_at if idx == 1 else planned_start - timedelta(seconds=lead_seconds)
    return create_at, planned_start, planned_end


class LessonEngine:
    def __init__(self, zoom, notifier: Notifier | None = None):
        self.zoom = zoom
        self.notifier = notifier or Notifier()
        self.lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._stop = asyncio.Event()
        self.s = get_settings()

    # ------------------------------------------------------------ akkaunt tanlash
    async def find_account(self, db, win_start: datetime, win_end: datetime,
                           exclude: set[int] | None = None,
                           ignore_block_id: int | None = None) -> ZoomAccount | None:
        buf = timedelta(minutes=self.s.account_buffer_minutes)
        busy_q = select(LessonBlock.account_id).where(
            LessonBlock.account_id.is_not(None),
            LessonBlock.status.in_(ACTIVE_BLOCK_STATES),
            LessonBlock.create_at < win_end + buf,
            LessonBlock.planned_end > win_start - buf,
        )
        if ignore_block_id:
            busy_q = busy_q.where(LessonBlock.id != ignore_block_id)
        busy = {r[0] for r in (await db.execute(busy_q)).all()}
        busy |= exclude or set()

        accs = (await db.execute(
            select(ZoomAccount).where(ZoomAccount.is_active.is_(True), ZoomAccount.status != "error")
        )).scalars().all()
        free = [a for a in accs if a.id not in busy]
        if not free:
            return None
        since = utcnow() - timedelta(hours=24)
        usage = dict((await db.execute(
            select(LessonBlock.account_id, func.count()).where(
                LessonBlock.created_real_at >= since).group_by(LessonBlock.account_id)
        )).all())
        free.sort(key=lambda a: (usage.get(a.id, 0), a.id))
        return free[0]

    async def capacity(self) -> dict:
        """Hozirgi paytda nechta akkaunt band/bo'sh."""
        async with session_factory()() as db:
            now = utcnow()
            total = (await db.execute(select(func.count()).select_from(ZoomAccount).where(
                ZoomAccount.is_active.is_(True)))).scalar_one()
            healthy = (await db.execute(select(func.count()).select_from(ZoomAccount).where(
                ZoomAccount.is_active.is_(True), ZoomAccount.status != "error"))).scalar_one()
            buf = timedelta(minutes=self.s.account_buffer_minutes)
            busy = (await db.execute(select(func.count(func.distinct(LessonBlock.account_id))).where(
                LessonBlock.status.in_(ACTIVE_BLOCK_STATES),
                LessonBlock.create_at < now + buf, LessonBlock.planned_end > now - buf))).scalar_one()
            return {"total": total, "healthy": healthy, "busy": busy, "free": max(healthy - busy, 0)}

    # ------------------------------------------------------------ darsni boshlash
    async def start_session(self, teacher_id: int, chat_id: int, blocks: int):
        """-> (session_id | None, xato matni | None)"""
        s = self.s
        if not 1 <= blocks <= s.max_blocks:
            return None, f"Bloklar soni 1 dan {s.max_blocks} gacha bo'lishi kerak."
        async with self.lock:
            async with session_factory()() as db:
                teacher = await db.get(Teacher, teacher_id)
                if not teacher or not teacher.is_active:
                    return None, "Sizga ruxsat berilmagan."
                active = (await db.execute(select(LessonSession.id).where(
                    LessonSession.teacher_id == teacher_id, LessonSession.status == "active"))).first()
                if active:
                    return None, "Sizda allaqachon faol dars bor."
                started = utcnow()
                sess = LessonSession(teacher_id=teacher_id, chat_id=chat_id, blocks_count=blocks,
                                     block_minutes=s.block_minutes, started_at=started, status="active")
                db.add(sess)
                await db.flush()
                for idx in range(1, blocks + 1):
                    create_at, ps, pe = block_times(started, idx, s.block_minutes, s.lead_seconds)
                    acc = await self.find_account(db, create_at, pe)
                    if not acc:
                        await db.rollback()
                        return None, ("Hozir bo'sh Zoom akkaunt yetarli emas. "
                                      "Bir oz kutib qayta urinib ko'ring yoki bloklar sonini kamaytiring.")
                    db.add(LessonBlock(session_id=sess.id, idx=idx, account_id=acc.id, status="reserved",
                                       create_at=create_at, planned_start=ps, planned_end=pe))
                    await db.flush()
                db.add(AuditLog(actor=f"teacher:{teacher.id}", action="session.start",
                                detail=f"session={sess.id} blocks={blocks}"))
                await db.commit()
                sid = sess.id
        first = (await self._next_block_id(sid, only_idx=1))
        if first:
            await self.process_block(first)
        return sid, None

    async def _next_block_id(self, session_id: int, only_idx: int | None = None):
        async with session_factory()() as db:
            q = select(LessonBlock.id).where(LessonBlock.session_id == session_id,
                                             LessonBlock.status == "reserved")
            if only_idx:
                q = q.where(LessonBlock.idx == only_idx)
            return (await db.execute(q.order_by(LessonBlock.idx).limit(1))).scalar_one_or_none()

    # ------------------------------------------------------------ blokni yaratish
    async def process_block(self, block_id: int) -> None:
        async with session_factory()() as db:
            res = await db.execute(update(LessonBlock).where(
                LessonBlock.id == block_id, LessonBlock.status == "reserved").values(status="creating"))
            await db.commit()
            if res.rowcount != 1:
                return
            block = (await db.execute(select(LessonBlock).where(LessonBlock.id == block_id)
                                      .options(selectinload(LessonBlock.account)))).scalar_one()
            sess = await db.get(LessonSession, block.session_id)
            teacher = await db.get(Teacher, sess.teacher_id)
            now = utcnow()
            if sess.status != "active":
                block.status = "cancelled"
                await db.commit()
                return
            if now >= block.planned_end:
                block.status = "missed"
                block.error = "Vaqti o'tib ketdi"
                await db.commit()
                return

            tried: set[int] = set()
            last_err = ""
            topic = f"{teacher.full_name} - {block.idx}/{sess.blocks_count}-blok"
            for _ in range(3):
                acc = block.account
                if acc is None or acc.id in tried:
                    acc = await self.find_account(db, now, block.planned_end, exclude=tried,
                                                  ignore_block_id=block.id)
                    if acc is None:
                        break
                    block.account_id = acc.id
                    block.account = acc
                tried.add(acc.id)
                block.attempts += 1
                try:
                    m = await self.zoom.create_meeting(acc, topic, sess.block_minutes)
                except ZoomError as e:
                    last_err = f"{acc.name}: {e}"
                    log.warning("Meeting yaratilmadi: %s", last_err)
                    if e.is_account_problem:
                        acc.status = "error"
                        acc.last_error = str(e)[:500]
                        await self.notifier.admin_alert(f"⚠️ Zoom akkaunt '{acc.name}' xato berdi: {e}")
                    block.account_id = None
                    block.account = None
                    await db.commit()
                    continue
                block.meeting_id = m["id"]
                block.join_url = m["join_url"]
                block.start_url = m["start_url"]
                block.passcode = m["passcode"]
                block.created_real_at = utcnow()
                block.status = "created"
                block.error = None
                acc.status = "ok"
                acc.last_error = None
                await db.commit()
                try:
                    await self.notifier.block_ready(sess, teacher, block)
                except Exception:
                    log.exception("Xabar yuborilmadi")
                return

            block.status = "failed"
            block.error = last_err or "Bo'sh akkaunt topilmadi"
            await db.commit()
            await self.notifier.teacher_error(
                sess, teacher, f"{block.idx}-blok uchun Zoom yig'ilish yaratib bo'lmadi. Administratorga murojaat qiling.")
            await self.notifier.admin_alert(
                f"❌ {teacher.full_name}: {block.idx}-blok yaratilmadi. {block.error}")

    # ------------------------------------------------------------ boshqaruv
    async def stop_session(self, session_id: int, actor: str = "teacher") -> bool:
        async with self.lock:
            async with session_factory()() as db:
                sess = (await db.execute(select(LessonSession).where(LessonSession.id == session_id)
                                         .options(selectinload(LessonSession.blocks)))).scalar_one_or_none()
                if not sess or sess.status != "active":
                    return False
                now = utcnow()
                to_delete = []
                for b in sess.blocks:
                    if b.status == "reserved":
                        b.status = "cancelled"
                    elif b.status == "created":
                        if b.planned_start > now:
                            b.status = "cancelled"
                            if b.meeting_id and b.account_id:
                                to_delete.append((b.account_id, b.meeting_id))
                        else:
                            b.status = "finished"
                    elif b.status == "creating":
                        b.status = "cancelled"
                await self._finalize(db, sess, now, status="cancelled", reason=actor)
                db.add(AuditLog(actor=actor, action="session.stop", detail=f"session={sess.id}"))
                await db.commit()
                teacher = await db.get(Teacher, sess.teacher_id)
                for acc_id, mid in to_delete:
                    acc = await db.get(ZoomAccount, acc_id)
                    try:
                        await self.zoom.delete_meeting(acc, mid)
                    except Exception:
                        log.warning("Meeting o'chirilmadi %s", mid)
        await self.notifier.session_finished(sess, teacher)
        return True

    async def extend_session(self, session_id: int):
        """+1 blok. -> (ok, xabar)"""
        async with self.lock:
            async with session_factory()() as db:
                sess = (await db.execute(select(LessonSession).where(LessonSession.id == session_id)
                                         .options(selectinload(LessonSession.blocks)))).scalar_one_or_none()
                if not sess or sess.status != "active":
                    return False, "Faol dars topilmadi."
                if sess.blocks_count >= self.s.max_blocks:
                    return False, f"Maksimal {self.s.max_blocks} blok."
                idx = sess.blocks_count + 1
                create_at, ps, pe = block_times(sess.started_at, idx, sess.block_minutes, self.s.lead_seconds)
                now = utcnow()
                last = max(sess.blocks, key=lambda b: b.idx)
                if last.planned_end <= now:
                    return False, "Dars vaqti tugagan, yangi dars boshlang."
                create_at = max(create_at, now) if create_at < now else create_at
                acc = await self.find_account(db, create_at, pe)
                if not acc:
                    return False, "Bo'sh Zoom akkaunt topilmadi."
                db.add(LessonBlock(session_id=sess.id, idx=idx, account_id=acc.id, status="reserved",
                                   create_at=create_at, planned_start=ps, planned_end=pe))
                sess.blocks_count = idx
                db.add(AuditLog(actor=f"session:{sess.id}", action="session.extend", detail=f"idx={idx}"))
                await db.commit()
                return True, f"{idx}-blok qo'shildi."

    async def send_next_now(self, session_id: int):
        """Keyingi blokni darhol yaratish. -> (ok, xabar)"""
        async with self.lock:
            async with session_factory()() as db:
                b = (await db.execute(select(LessonBlock).where(
                    LessonBlock.session_id == session_id, LessonBlock.status == "reserved")
                    .order_by(LessonBlock.idx).limit(1))).scalar_one_or_none()
                if not b:
                    return False, "Keyingi blok yo'q."
                sess = await db.get(LessonSession, session_id)
                if sess.status != "active":
                    return False, "Dars faol emas."
                now = utcnow()
                acc = await self.find_account(db, now, b.planned_end, ignore_block_id=b.id)
                if not acc:
                    return False, "Hozir bo'sh akkaunt yo'q."
                b.account_id = acc.id
                b.create_at = now
                await db.commit()
                bid = b.id
        await self.process_block(bid)
        return True, "Keyingi blok yuborildi."

    async def _finalize(self, db, sess: LessonSession, now: datetime, status: str, reason: str | None = None):
        sess.status = status
        sess.ended_at = now
        elapsed = int((now - sess.started_at).total_seconds() // 60)
        sess.actual_minutes = max(0, min(sess.planned_minutes, elapsed))
        sess.stop_reason = reason

    # ------------------------------------------------------------ scheduler
    async def tick(self) -> None:
        now = utcnow()
        async with session_factory()() as db:
            due = (await db.execute(select(LessonBlock.id).where(
                LessonBlock.status == "reserved", LessonBlock.create_at <= now)
                .order_by(LessonBlock.create_at))).scalars().all()
            # tugagan blok -> finished
            await db.execute(update(LessonBlock).where(
                LessonBlock.status == "created", LessonBlock.planned_end <= now).values(status="finished"))
            # qotib qolgan 'creating'
            await db.execute(update(LessonBlock).where(
                LessonBlock.status == "creating", LessonBlock.create_at <= now - timedelta(minutes=2))
                .values(status="reserved"))
            await db.commit()
        for bid in due:
            t = asyncio.create_task(self.process_block(bid))
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)
        await self._finalize_done()

    async def _finalize_done(self):
        finished: list[tuple[LessonSession, Teacher]] = []
        async with self.lock:
            async with session_factory()() as db:
                sessions = (await db.execute(select(LessonSession).where(LessonSession.status == "active")
                                             .options(selectinload(LessonSession.blocks)))).scalars().all()
                now = utcnow()
                for sess in sessions:
                    if any(b.status in ACTIVE_BLOCK_STATES for b in sess.blocks):
                        continue
                    ok = any(b.status == "finished" for b in sess.blocks)
                    await self._finalize(db, sess, now, "completed" if ok else "failed",
                                         None if ok else "no_blocks")
                    teacher = await db.get(Teacher, sess.teacher_id)
                    finished.append((sess, teacher))
                await db.commit()
        for sess, teacher in finished:
            try:
                await self.notifier.session_finished(sess, teacher)
            except Exception:
                log.exception("Yakun xabari yuborilmadi")

    async def recover(self):
        """Ishga tushganda: 'creating' holatini qaytarish."""
        async with session_factory()() as db:
            await db.execute(update(LessonBlock).where(LessonBlock.status == "creating")
                             .values(status="reserved"))
            await db.commit()

    async def run(self):
        await self.recover()
        log.info("Scheduler ishga tushdi")
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:
                log.exception("Scheduler xatosi")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass

    def stop(self):
        self._stop.set()
