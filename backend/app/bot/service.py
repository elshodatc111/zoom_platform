"""Telegram bot (aiogram 3, long polling). Matnlar o'zbek tilida."""
import html
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                           Message, ReplyKeyboardMarkup)
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from ..core.config import get_settings
from ..core.timeutil import fmt_time
from ..db.base import session_factory
from ..db.models import LessonBlock, LessonSession, Teacher, ZoomAccount
from ..services import stats
from ..services.engine import LessonEngine, Notifier

log = logging.getLogger("bot")

BTN_START = "▶️ Dars boshlash"
BTN_CURRENT = "📍 Joriy dars"
BTN_STATS = "📊 Statistikam"
MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_START)], [KeyboardButton(text=BTN_CURRENT), KeyboardButton(text=BTN_STATS)]],
    resize_keyboard=True,
)


def controls(sid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Keyingisini hozir yuborish", callback_data=f"next:{sid}")],
        [InlineKeyboardButton(text="➕ +1 blok", callback_data=f"ext:{sid}"),
         InlineKeyboardButton(text="⏹ To'xtatish", callback_data=f"stop:{sid}")],
    ])


def fmt_minutes(m: int) -> str:
    h, mm = divmod(m, 60)
    return f"{h} soat {mm} daq" if h and mm else (f"{h} soat" if h else f"{mm} daq")


class BotService(Notifier):
    def __init__(self, engine: LessonEngine):
        self.engine = engine
        self.s = get_settings()
        self.bot: Bot | None = None
        self.dp: Dispatcher | None = None
        if self.s.bot_token:
            self.bot = Bot(self.s.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            self.dp = Dispatcher()
            self.dp.include_router(self._router())
        engine.notifier = self

    # ------------------------------------------------------------ yordamchilar
    async def _send(self, chat_id: int, text: str, markup=None):
        if not self.bot:
            return
        try:
            await self.bot.send_message(chat_id, text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramAPIError as e:
            log.warning("Telegram xabar yuborilmadi (%s): %s", chat_id, e)

    async def _teacher(self, user_id: int, username: str | None) -> Teacher | None:
        async with session_factory()() as db:
            t = (await db.execute(select(Teacher).where(Teacher.telegram_id == user_id))).scalar_one_or_none()
            if not t and username:
                t = (await db.execute(select(Teacher).where(
                    Teacher.telegram_id.is_(None), Teacher.tg_username.ilike(username.lstrip("@"))
                ))).scalar_one_or_none()
                if t:
                    t.telegram_id = user_id
                    await db.commit()
            return t if t and t.is_active else None

    async def _active_session(self, teacher_id: int):
        async with session_factory()() as db:
            return (await db.execute(select(LessonSession).where(
                LessonSession.teacher_id == teacher_id, LessonSession.status == "active")
                .options(selectinload(LessonSession.blocks)))).scalar_one_or_none()

    # ------------------------------------------------------------ Notifier
    async def block_ready(self, session, teacher, block):
        # 1) Faqat o'qituvchi uchun: host havolasi + boshqaruv tugmalari
        head = (f"🎥 <b>{block.idx}/{session.blocks_count}-blok</b>" if block.idx == 1
                else f"🔔 <b>Keyingi blok: {block.idx}/{session.blocks_count}</b>")
        host = (f"{head}\n⏱ {fmt_time(block.planned_start)} – {fmt_time(block.planned_end)}\n\n"
                f"👨‍🏫 <b>Siz uchun (host, kirish):</b>\n{html.escape(block.start_url)}")
        if block.idx < session.blocks_count:
            host += "\n\n<i>Keyingi havola bu blok tugashiga 1 daqiqa qolganda keladi.</i>"
        host += "\n\n👇 <i>Pastdagi xabarni talabalar guruhiga forward qiling.</i>"
        await self._send(session.chat_id, host, controls(session.id))

        # 2) Talabalar uchun: alohida, toza xabar (guruhga forward qilish uchun)
        stud = (f"📚 <b>Dars: {html.escape(teacher.full_name)}</b>\n"
                f"⏱ {fmt_time(block.planned_start)} – {fmt_time(block.planned_end)}"
                f" ({block.idx}/{session.blocks_count}-qism)\n\n"
                f"🔗 <b>Zoom havolasi:</b>\n{html.escape(block.join_url)}\n\n"
                f"🆔 Meeting ID: <code>{block.meeting_id}</code>")
        if block.passcode:
            stud += f"\n🔑 Parol: <code>{html.escape(block.passcode)}</code>"
        await self._send(session.chat_id, stud)

    async def session_finished(self, session, teacher):
        mins = session.actual_minutes or 0
        icon = "⏹ Dars to'xtatildi" if session.status == "cancelled" else "✅ Dars yakunlandi"
        await self._send(session.chat_id, f"{icon}\nDavomiyligi: <b>{fmt_minutes(mins)}</b>", MENU)

    async def teacher_error(self, session, teacher, text):
        await self._send(session.chat_id, f"⚠️ {html.escape(text)}")

    async def admin_alert(self, text: str):
        for aid in self.s.admin_ids:
            await self._send(aid, html.escape(text))

    # ------------------------------------------------------------ handlerlar
    def _router(self) -> Router:
        r = Router()

        @r.message(CommandStart())
        async def start(m: Message):
            t = await self._teacher(m.from_user.id, m.from_user.username)
            if not t:
                await m.answer(f"Sizga botdan foydalanish uchun ruxsat berilmagan.\n"
                               f"Administratorga ID raqamingizni yuboring: <code>{m.from_user.id}</code>")
                return
            await m.answer(f"Assalomu alaykum, <b>{html.escape(t.full_name)}</b>!\nQuyidagi menyudan foydalaning.",
                           reply_markup=MENU)

        @r.message(Command("id"))
        async def my_id(m: Message):
            await m.answer(f"Sizning ID: <code>{m.from_user.id}</code>")

        @r.message(F.text == BTN_START)
        async def begin(m: Message):
            t = await self._teacher(m.from_user.id, m.from_user.username)
            if not t:
                return await m.answer("Ruxsat yo'q.")
            if await self._active_session(t.id):
                return await m.answer("Sizda faol dars bor. «📍 Joriy dars» tugmasini bosing.")
            n = self.s.max_blocks
            rows, row = [], []
            for k in range(1, n + 1):
                row.append(InlineKeyboardButton(text=str(k), callback_data=f"n:{k}"))
                if len(row) == 5:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            await m.answer(f"Necha blok kerak? (1 blok = {self.s.block_minutes} daqiqa)",
                           reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

        @r.callback_query(F.data.startswith("n:"))
        async def pick(c: CallbackQuery):
            k = int(c.data.split(":")[1])
            total = k * self.s.block_minutes
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="▶️ Boshlash", callback_data=f"go:{k}"),
                InlineKeyboardButton(text="✖️ Bekor", callback_data="cancel")]])
            await c.message.edit_text(f"<b>{k} blok</b> = {fmt_minutes(total)}\nBoshlaymizmi?", reply_markup=kb)
            await c.answer()

        @r.callback_query(F.data == "cancel")
        async def cancel(c: CallbackQuery):
            await c.message.edit_text("Bekor qilindi.")
            await c.answer()

        @r.callback_query(F.data.startswith("go:"))
        async def go(c: CallbackQuery):
            t = await self._teacher(c.from_user.id, c.from_user.username)
            if not t:
                return await c.answer("Ruxsat yo'q", show_alert=True)
            k = int(c.data.split(":")[1])
            await c.answer("Zoom tayyorlanmoqda…")
            await c.message.edit_text("⏳ Zoom yig'ilish yaratilmoqda…")
            sid, err = await self.engine.start_session(t.id, c.message.chat.id, k)
            if err:
                await c.message.edit_text(f"❌ {html.escape(err)}")
            else:
                await c.message.edit_text(f"✅ Dars boshlandi ({k} blok).")

        async def own_session(c: CallbackQuery) -> int | None:
            t = await self._teacher(c.from_user.id, c.from_user.username)
            sid = int(c.data.split(":")[1])
            if not t:
                await c.answer("Ruxsat yo'q", show_alert=True)
                return None
            async with session_factory()() as db:
                s = await db.get(LessonSession, sid)
            if not s or s.teacher_id != t.id or s.status != "active":
                await c.answer("Bu dars faol emas", show_alert=True)
                return None
            return sid

        @r.callback_query(F.data.startswith("next:"))
        async def nxt(c: CallbackQuery):
            sid = await own_session(c)
            if sid:
                ok, msg = await self.engine.send_next_now(sid)
                await c.answer(msg, show_alert=not ok)

        @r.callback_query(F.data.startswith("ext:"))
        async def ext(c: CallbackQuery):
            sid = await own_session(c)
            if sid:
                ok, msg = await self.engine.extend_session(sid)
                await c.answer(msg, show_alert=not ok)

        @r.callback_query(F.data.startswith("stop:"))
        async def stop_ask(c: CallbackQuery):
            sid = await own_session(c)
            if sid:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Ha, to'xtatish", callback_data=f"stopyes:{sid}"),
                    InlineKeyboardButton(text="Yo'q", callback_data="cancel")]])
                await c.message.answer("Darsni to'xtatmoqchimisiz? Kelgusi havolalar bekor qilinadi.", reply_markup=kb)
                await c.answer()

        @r.callback_query(F.data.startswith("stopyes:"))
        async def stop_yes(c: CallbackQuery):
            sid = await own_session(c)
            if sid:
                await self.engine.stop_session(sid, actor="teacher")
                await c.message.edit_text("Dars to'xtatildi.")
                await c.answer()

        @r.message(F.text == BTN_CURRENT)
        async def current(m: Message):
            t = await self._teacher(m.from_user.id, m.from_user.username)
            if not t:
                return await m.answer("Ruxsat yo'q.")
            s = await self._active_session(t.id)
            if not s:
                return await m.answer("Hozir faol dars yo'q.")
            icons = {"reserved": "⏳", "creating": "⏳", "created": "🟢", "finished": "✔️",
                     "failed": "❌", "cancelled": "🚫", "missed": "⚠️"}
            lines = [f"<b>Joriy dars</b> — {s.blocks_count} blok"]
            for b in s.blocks:
                lines.append(f"{icons.get(b.status, '•')} {b.idx}-blok  {fmt_time(b.planned_start)}–{fmt_time(b.planned_end)}")
            await m.answer("\n".join(lines), reply_markup=controls(s.id))

        @r.message(F.text == BTN_STATS)
        async def my_stats(m: Message):
            t = await self._teacher(m.from_user.id, m.from_user.username)
            if not t:
                return await m.answer("Ruxsat yo'q.")
            async with session_factory()() as db:
                d1 = await stats.summary(db, *stats.day_range(1), teacher_id=t.id)
                d7 = await stats.summary(db, *stats.day_range(7), teacher_id=t.id)
                mo = await stats.summary(db, stats.month_start(), stats.day_range(1)[1], teacher_id=t.id)
            def line(label, d):
                return f"<b>{label}:</b> {d['sessions']} dars, {fmt_minutes(d['actual_minutes'])}"
            await m.answer("📊 <b>Statistikangiz</b>\n" + "\n".join([
                line("Bugun", d1), line("Oxirgi 7 kun", d7), line("Shu oy", mo)]))

        # --- admin buyruqlari
        def is_admin(m: Message) -> bool:
            return m.from_user.id in self.s.admin_ids

        @r.message(Command("faol"))
        async def active(m: Message):
            if not is_admin(m):
                return
            async with session_factory()() as db:
                rows = (await db.execute(select(LessonSession).where(LessonSession.status == "active")
                        .options(selectinload(LessonSession.teacher), selectinload(LessonSession.blocks)))).scalars().all()
            if not rows:
                return await m.answer("Faol dars yo'q.")
            out = []
            for s in rows:
                done = sum(1 for b in s.blocks if b.status in ("created", "finished"))
                out.append(f"• {html.escape(s.teacher.full_name)} — {done}/{s.blocks_count} blok, "
                           f"boshlangan {fmt_time(s.started_at)}")
            await m.answer("<b>Faol darslar</b>\n" + "\n".join(out))

        @r.message(Command("akkauntlar"))
        async def accounts(m: Message):
            if not is_admin(m):
                return
            cap = await self.engine.capacity()
            async with session_factory()() as db:
                accs = (await db.execute(select(ZoomAccount).order_by(ZoomAccount.name))).scalars().all()
            lines = [f"{'🟢' if a.status == 'ok' else '🔴' if a.status == 'error' else '⚪'} {html.escape(a.name)}"
                     f"{'' if a.is_active else ' (o‘chirilgan)'}" for a in accs]
            await m.answer(f"<b>Akkauntlar:</b> jami {cap['total']}, bo'sh {cap['free']}, band {cap['busy']}\n"
                           + "\n".join(lines))

        return r

    # ------------------------------------------------------------ ishga tushirish
    async def run(self):
        if not self.bot:
            log.warning("BOT_TOKEN yo'q: Telegram bot ishga tushmadi")
            return
        me = await self.bot.get_me()
        log.info("Bot ishga tushdi: @%s", me.username)
        await self.dp.start_polling(self.bot, handle_signals=False)

    async def close(self):
        if self.dp:
            try:
                await self.dp.stop_polling()
            except Exception:
                pass
        if self.bot:
            await self.bot.session.close()
