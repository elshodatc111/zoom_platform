import os
from datetime import timedelta

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import encrypt  # noqa: E402
from app.db import base  # noqa: E402
from app.db.models import LessonBlock, LessonSession, Teacher, ZoomAccount  # noqa: E402
from app.services.engine import LessonEngine, Notifier  # noqa: E402
from app.services.zoom_client import ZoomError  # noqa: E402

pytestmark = pytest.mark.asyncio(loop_scope="function")


class FakeZoom:
    def __init__(self):
        self.n = 0
        self.fail_accounts: set[str] = set()
        self.deleted = []

    async def create_meeting(self, acc, topic, duration):
        if acc.name in self.fail_accounts:
            raise ZoomError("boom", 401)
        self.n += 1
        return {"id": str(self.n), "join_url": f"https://zoom/j/{self.n}",
                "start_url": f"https://zoom/s/{self.n}", "passcode": "x"}

    async def delete_meeting(self, acc, mid):
        self.deleted.append(mid)


class Rec(Notifier):
    def __init__(self):
        self.ready, self.fin, self.alerts = [], [], []

    async def block_ready(self, s, t, b):
        self.ready.append(b.idx)

    async def session_finished(self, s, t):
        self.fin.append(s.id)

    async def admin_alert(self, text):
        self.alerts.append(text)


@pytest_asyncio.fixture
async def env(tmp_path):
    get_settings.cache_clear()
    if os.path.exists("test.db"):
        os.remove("test.db")
    base.init_engine("sqlite+aiosqlite:///./test.db")
    await base.create_all()
    async with base.session_factory()() as db:
        for i in range(3):
            db.add(ZoomAccount(name=f"a{i}", email=f"a{i}@x.com", zoom_account_id="z", client_id="c",
                               client_secret_enc=encrypt("s")))
        db.add(Teacher(full_name="T1", telegram_id=1))
        db.add(Teacher(full_name="T2", telegram_id=2))
        db.add(Teacher(full_name="T3", telegram_id=3))
        await db.commit()
    zoom, rec = FakeZoom(), Rec()
    yield LessonEngine(zoom, rec), zoom, rec
    await base.get_engine().dispose()


async def blocks(sid):
    async with base.session_factory()() as db:
        return (await db.execute(select(LessonBlock).where(LessonBlock.session_id == sid)
                                 .order_by(LessonBlock.idx))).scalars().all()


async def test_three_blocks_alternate_two_accounts(env):
    eng, zoom, rec = env
    sid, err = await eng.start_session(1, 100, 3)
    assert err is None
    bl = await blocks(sid)
    assert [b.status for b in bl] == ["created", "reserved", "reserved"]
    assert bl[0].account_id != bl[1].account_id
    assert bl[2].account_id == bl[0].account_id  # 3-blok 1-akkauntdan qayta foydalanadi
    assert (bl[1].create_at - bl[0].create_at) == timedelta(minutes=40) - timedelta(seconds=60)
    assert rec.ready == [1]


async def test_scheduler_creates_next_block(env):
    eng, zoom, rec = env
    sid, _ = await eng.start_session(1, 100, 2)
    async with base.session_factory()() as db:
        b = (await db.execute(select(LessonBlock).where(LessonBlock.session_id == sid,
                                                        LessonBlock.idx == 2))).scalar_one()
        b.create_at = b.create_at - timedelta(minutes=60)
        await db.commit()
    await eng.tick()
    import asyncio
    await asyncio.sleep(0.2)
    assert rec.ready == [1, 2]


async def test_parallel_lessons_need_separate_accounts(env):
    eng, *_ = env
    assert (await eng.start_session(1, 100, 2))[1] is None  # 2 akkaunt
    assert (await eng.start_session(2, 101, 1))[1] is None  # 3-akkaunt
    sid, err = await eng.start_session(3, 102, 1)
    assert sid is None and "bo'sh" in err


async def test_one_active_session_per_teacher(env):
    eng, *_ = env
    await eng.start_session(1, 100, 1)
    _, err = await eng.start_session(1, 100, 1)
    assert err and "faol dars" in err


async def test_failover_to_other_account(env):
    eng, zoom, rec = env
    zoom.fail_accounts = {"a0"}
    sid, err = await eng.start_session(1, 100, 1)
    assert err is None
    bl = await blocks(sid)
    assert bl[0].status == "created"
    async with base.session_factory()() as db:
        a0 = (await db.execute(select(ZoomAccount).where(ZoomAccount.name == "a0"))).scalar_one()
        assert a0.status == "error"
    assert rec.alerts


async def test_stop_cancels_future_blocks(env):
    eng, zoom, rec = env
    sid, _ = await eng.start_session(1, 100, 3)
    assert await eng.stop_session(sid)
    bl = await blocks(sid)
    assert [b.status for b in bl] == ["finished", "cancelled", "cancelled"]
    async with base.session_factory()() as db:
        s = await db.get(LessonSession, sid)
        assert s.status == "cancelled" and s.actual_minutes <= 1
    assert rec.fin == [sid]


async def test_extend_and_send_next(env):
    eng, zoom, rec = env
    sid, _ = await eng.start_session(1, 100, 1)
    ok, _ = await eng.extend_session(sid)
    assert ok
    ok, _ = await eng.send_next_now(sid)
    assert ok
    assert rec.ready == [1, 2]
    bl = await blocks(sid)
    assert bl[0].account_id != bl[1].account_id


async def test_finalize_when_blocks_end(env):
    eng, zoom, rec = env
    sid, _ = await eng.start_session(1, 100, 1)
    async with base.session_factory()() as db:
        s = await db.get(LessonSession, sid)
        b = (await blocks(sid))[0]
        b = await db.get(LessonBlock, b.id)
        b.planned_end = b.planned_end - timedelta(minutes=41)
        await db.commit()
    await eng.tick()
    async with base.session_factory()() as db:
        s = await db.get(LessonSession, sid)
        assert s.status == "completed"
    assert rec.fin == [sid]
