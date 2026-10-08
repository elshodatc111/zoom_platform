from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decode_token
from ..db.base import get_db
from ..db.models import Admin, AuditLog

COOKIE = "zp_session"


async def current_admin(request: Request, db: AsyncSession = Depends(get_db)) -> Admin:
    token = request.cookies.get(COOKIE)
    admin_id = decode_token(token) if token else None
    admin = await db.get(Admin, admin_id) if admin_id else None
    if not admin or not admin.is_active:
        raise HTTPException(401, "Kirish talab qilinadi")
    return admin


async def audit(db: AsyncSession, admin: Admin, action: str, detail: str = ""):
    db.add(AuditLog(actor=f"admin:{admin.username}", action=action, detail=detail))
