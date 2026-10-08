"""backend/.env ni yaratadi (kerak bo'lsa) va bo'sh JWT_SECRET / FERNET_KEY ni to'ldiradi."""
import base64
import os
import re
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src, dst = root / ".env.example", root / ".env"

if not dst.exists():
    dst.write_bytes(src.read_bytes())
    print(".env yaratildi")

text = dst.read_text(encoding="utf-8")


def fill(key: str, value: str, text: str) -> tuple[str, bool]:
    pat = re.compile(rf"^{key}=[ \t]*(\r?)$", re.M)
    if pat.search(text):
        return pat.sub(lambda m: f"{key}={value}{m.group(1)}", text, count=1), True
    if not re.search(rf"^{key}=", text, re.M):
        return text.rstrip("\r\n") + f"\n{key}={value}\n", True
    return text, False


changed = False
text, c1 = fill("JWT_SECRET", secrets.token_urlsafe(48), text)
text, c2 = fill("FERNET_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode(), text)
if c1 or c2:
    dst.write_text(text, encoding="utf-8", newline="")
    print("Sirlar (JWT_SECRET / FERNET_KEY) avtomatik yaratildi")
