import asyncio
import logging
import logging.handlers
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .bot.service import BotService
from .core.config import BASE_DIR, get_settings
from .db.base import create_all, get_engine
from .services.engine import LessonEngine
from .services.maintenance import health_loop, monthly_report_loop
from .services.zoom_client import ZoomClient

FRONT_DIST = BASE_DIR.parent / "frontend" / "dist"


def setup_logging():
    logs = BASE_DIR / "logs"
    logs.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = logging.handlers.RotatingFileHandler(logs / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [fh, sh]


async def _guard(name: str, coro_fn, *args):
    """Fon vazifa yiqilsa, 5 soniyadan keyin qayta ishga tushiradi."""
    while True:
        try:
            await coro_fn(*args)
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(name).exception("%s yiqildi, qayta ishga tushirilmoqda", name)
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    cfg = get_settings()
    if cfg.database_url.startswith('mysql') and (cfg.jwt_secret.startswith('dev-secret') or not cfg.fernet_key):
        raise RuntimeError('.env da JWT_SECRET va FERNET_KEY sozlanmagan (python scripts/gen_secrets.py)')
    await create_all()
    zoom = ZoomClient()
    engine = LessonEngine(zoom)
    bot = BotService(engine)
    app.state.zoom, app.state.engine, app.state.bot = zoom, engine, bot
    tasks = [
        asyncio.create_task(_guard("scheduler", engine.run)),
        asyncio.create_task(_guard("bot", bot.run)),
        asyncio.create_task(health_loop(zoom, bot)),
        asyncio.create_task(monthly_report_loop(bot)),
    ]
    try:
        yield
    finally:
        engine.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bot.close()
        await zoom.close()
        await get_engine().dispose()


app = FastAPI(title="Zoom Platform", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router)


@app.get("/api/health")
async def health():
    return {"ok": True}


if FRONT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONT_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    async def spa(path: str):
        f = (FRONT_DIST / path).resolve()
        if path and f.is_file() and FRONT_DIST in f.parents:
            return FileResponse(f)
        return FileResponse(FRONT_DIST / "index.html")
