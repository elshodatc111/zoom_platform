"""Birinchi adminni yaratish: python scripts/create_admin.py <login> [parol]"""
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import create_all, session_factory
from app.db.models import Admin


async def main():
    if len(sys.argv) < 2:
        print("Foydalanish: python scripts/create_admin.py <login> [parol]")
        return
    username = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else getpass.getpass("Parol: ")
    if len(password) < 8:
        print("Parol kamida 8 belgi bo'lsin")
        return
    await create_all()
    async with session_factory()() as db:
        existing = (await db.execute(select(Admin).where(Admin.username == username))).scalar_one_or_none()
        if existing:
            existing.password_hash = hash_password(password)
            existing.is_active = True
            print("Mavjud admin paroli yangilandi")
        else:
            db.add(Admin(username=username, password_hash=hash_password(password)))
            print("Admin yaratildi")
        await db.commit()


asyncio.run(main())
