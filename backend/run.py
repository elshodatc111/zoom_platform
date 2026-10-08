"""Ishga tushirish: python run.py"""
import asyncio
import os
import sys

import uvicorn

from app.core.config import get_settings

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    s = get_settings()
    # Alwaysdata dasturga IP va PORT muhit o'zgaruvchilarini beradi
    host = os.environ.get("IP") or s.host
    uvicorn.run("app.main:app", host=host, port=s.port, log_level="info", proxy_headers=True, forwarded_allow_ips="*")
