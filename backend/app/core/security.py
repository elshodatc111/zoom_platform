import time
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from cryptography.fernet import Fernet

from .config import get_settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(admin_id: int) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(hours=s.jwt_hours)
    return jwt.encode({"sub": str(admin_id), "exp": exp}, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> int | None:
    try:
        data = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        return int(data["sub"])
    except Exception:
        return None


def _fernet() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise RuntimeError("FERNET_KEY .env da sozlanmagan (scripts/gen_secrets.py ni ishga tushiring)")
    return Fernet(key.encode())


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


class LoginLimiter:
    """Oddiy xotiradagi urinishlar cheklovi (LAN uchun brute-force himoyasi)."""

    def __init__(self, max_attempts: int = 5, window: int = 900):
        self.max = max_attempts
        self.window = window
        self.hits: dict[str, list[float]] = {}

    def _clean(self, key: str) -> list[float]:
        now = time.time()
        lst = [t for t in self.hits.get(key, []) if now - t < self.window]
        self.hits[key] = lst
        return lst

    def blocked(self, key: str) -> bool:
        return len(self._clean(key)) >= self.max

    def fail(self, key: str) -> None:
        self._clean(key).append(time.time())

    def reset(self, key: str) -> None:
        self.hits.pop(key, None)


login_limiter = LoginLimiter()
