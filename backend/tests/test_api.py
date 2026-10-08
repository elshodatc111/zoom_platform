import os

import pytest
from cryptography.fernet import Fernet

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_api.db"
os.environ["BOT_TOKEN"] = ""

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import base  # noqa: E402
from app.db.models import Admin  # noqa: E402


@pytest.fixture
async def client():
    get_settings.cache_clear()
    if os.path.exists("test_api.db"):
        os.remove("test_api.db")
    base.init_engine("sqlite+aiosqlite:///./test_api.db")
    from app.main import app
    async with app.router.lifespan_context(app):
        async with base.session_factory()() as db:
            db.add(Admin(username="root", password_hash=hash_password("password123")))
            await db.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            yield c


async def test_auth_and_crud(client):
    assert (await client.get("/api/teachers")).status_code == 401
    assert (await client.post("/api/auth/login", json={"username": "root", "password": "bad"})).status_code == 401
    assert (await client.post("/api/auth/login", json={"username": "root", "password": "password123"})).status_code == 200

    r = await client.post("/api/teachers", json={"full_name": "Ali Valiyev", "telegram_id": 555})
    assert r.status_code == 200
    assert (await client.post("/api/teachers", json={"full_name": "Dup", "telegram_id": 555})).status_code == 409
    assert (await client.post("/api/teachers", json={"full_name": "NoId"})).status_code == 400

    r = await client.post("/api/accounts", json={"name": "z1", "email": "a@b.c", "zoom_account_id": "x",
                                                  "client_id": "y", "client_secret": "secret"})
    assert r.status_code == 200 and "client_secret" not in r.text

    assert len((await client.get("/api/teachers")).json()) == 1
    assert len((await client.get("/api/accounts")).json()) == 1
    d = (await client.get("/api/dashboard")).json()
    assert d["capacity"]["total"] == 1 and d["bot_running"] is False
    assert (await client.get("/api/stats/teachers")).status_code == 200
    assert (await client.get("/api/stats/timeseries?group=week")).status_code == 200
    x = await client.get("/api/stats/export")
    assert x.status_code == 200 and x.content[:2] == b"PK"
    assert (await client.get("/api/sessions")).json()["total"] == 0
    assert (await client.get("/api/audit")).json()["total"] >= 3
