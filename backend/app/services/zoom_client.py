"""Zoom Server-to-Server OAuth klienti (har bir akkaunt uchun alohida token)."""
import time
from datetime import datetime, timezone

import httpx

from ..core.security import decrypt
from ..db.models import ZoomAccount

TOKEN_URL = "https://zoom.us/oauth/token"
API = "https://api.zoom.us/v2"


class ZoomError(Exception):
    def __init__(self, message: str, status: int | None = None, code: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code

    @property
    def is_account_problem(self) -> bool:
        """Akkauntning o'zida muammo (kalit, ruxsat) - boshqasiga o'tish kerak."""
        return self.status in (400, 401, 403, 404, 429) or (self.status or 0) >= 500


class ZoomClient:
    def __init__(self):
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0))
        self._tokens: dict[int, tuple[str, float]] = {}

    async def close(self):
        await self._http.aclose()

    def invalidate(self, account_id: int):
        self._tokens.pop(account_id, None)

    async def _token(self, acc: ZoomAccount) -> str:
        cached = self._tokens.get(acc.id)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        try:
            r = await self._http.post(
                TOKEN_URL,
                params={"grant_type": "account_credentials", "account_id": acc.zoom_account_id},
                auth=(acc.client_id, decrypt(acc.client_secret_enc)),
            )
        except httpx.HTTPError as e:
            raise ZoomError(f"Zoom bilan aloqa yo'q: {e}") from e
        if r.status_code != 200:
            raise ZoomError(f"Token olinmadi ({r.status_code}): {r.text[:200]}", r.status_code)
        data = r.json()
        self._tokens[acc.id] = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
        return data["access_token"]

    async def _request(self, acc: ZoomAccount, method: str, path: str, **kw):
        for attempt in (1, 2):
            token = await self._token(acc)
            try:
                r = await self._http.request(
                    method, f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, **kw
                )
            except httpx.HTTPError as e:
                raise ZoomError(f"Zoom bilan aloqa yo'q: {e}") from e
            if r.status_code == 401 and attempt == 1:
                self.invalidate(acc.id)
                continue
            if r.status_code >= 300:
                try:
                    j = r.json()
                except Exception:
                    j = {}
                raise ZoomError(j.get("message") or r.text[:200], r.status_code, j.get("code"))
            return r.json() if r.content else {}

    def _user(self, acc: ZoomAccount) -> str:
        return acc.email or "me"

    async def test(self, acc: ZoomAccount) -> dict:
        """Ulanishni tekshirish: foydalanuvchi ma'lumotini oladi."""
        u = await self._request(acc, "GET", f"/users/{self._user(acc)}")
        return {"email": u.get("email"), "type": u.get("type"), "plan": u.get("type")}

    async def create_meeting(self, acc: ZoomAccount, topic: str, duration: int) -> dict:
        body = {
            "topic": topic[:200],
            "type": 2,
            "start_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration": duration,
            "timezone": "UTC",
            "settings": {
                "join_before_host": True,
                "waiting_room": False,
                "host_video": True,
                "participant_video": False,
                "mute_upon_entry": True,
                "approval_type": 2,
                "auto_recording": "none",
            },
        }
        m = await self._request(acc, "POST", f"/users/{self._user(acc)}/meetings", json=body)
        return {
            "id": str(m["id"]),
            "join_url": m["join_url"],
            "start_url": m["start_url"],
            "passcode": m.get("password") or "",
        }

    async def delete_meeting(self, acc: ZoomAccount, meeting_id: str) -> None:
        await self._request(acc, "DELETE", f"/meetings/{meeting_id}")
