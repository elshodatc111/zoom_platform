"""MySQL ulanishini tekshiradi. Ulanmasa, root orqali baza va foydalanuvchini o'zi yaratib, .env ni yangilaydi."""
import getpass
import re
import secrets
import string
import sys
from pathlib import Path

import pymysql
from sqlalchemy.engine import make_url

ENV = Path(__file__).resolve().parents[1] / ".env"


def read_url() -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    return ""


def can_connect(u) -> str | None:
    try:
        pymysql.connect(host=u.host or "127.0.0.1", port=u.port or 3306, user=u.username,
                        password=u.password or "", database=u.database).close()
        return None
    except Exception as e:
        return str(e)


def main() -> int:
    raw = read_url()
    if not raw.startswith("mysql"):
        print("DATABASE_URL MySQL emas, tekshiruv o'tkazib yuborildi.")
        return 0
    u = make_url(raw)
    err = can_connect(u)
    if err is None:
        return 0

    print("\nMySQL ga ulanib bo'lmadi:", err)
    print("Baza va foydalanuvchini avtomatik yarata olaman (MySQL root paroli kerak).")
    root_user = input("MySQL admin login [root]: ").strip() or "root"
    root_pw = getpass.getpass("MySQL admin paroli (bo'sh bo'lsa Enter; o'tkazib yuborish uchun Ctrl+C): ")
    try:
        conn = pymysql.connect(host=u.host or "127.0.0.1", port=u.port or 3306, user=root_user, password=root_pw)
    except Exception as e:
        print("Admin sifatida ulanib bo'lmadi:", e)
        return 1

    user = u.username or "zoom"
    db = u.database or "zoomplatform"
    if not re.fullmatch(r"\w+", user) or not re.fullmatch(r"\w+", db):
        print("Baza yoki foydalanuvchi nomida mumkin bo'lmagan belgilar bor.")
        return 1
    pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        qpw = conn.escape(pw)  # parol tirnoqli, xavfsiz holda
        for host in ("localhost", "127.0.0.1", "%"):
            acct = f"'{user}'@'{host}'"
            cur.execute(f"CREATE USER IF NOT EXISTS {acct} IDENTIFIED BY {qpw}")
            cur.execute(f"ALTER USER {acct} IDENTIFIED BY {qpw}")
            cur.execute(f"GRANT ALL PRIVILEGES ON `{db}`.* TO {acct}")
        cur.execute("FLUSH PRIVILEGES")
    conn.commit()
    conn.close()

    new_url = f"mysql+aiomysql://{user}:{pw}@{u.host or '127.0.0.1'}:{u.port or 3306}/{db}"
    text = ENV.read_text(encoding="utf-8")
    text = re.sub(r"^DATABASE_URL=.*$", lambda m: f"DATABASE_URL={new_url}", text, flags=re.M)
    ENV.write_text(text, encoding="utf-8")

    err = can_connect(make_url(new_url))
    if err:
        print("Baza yaratildi, lekin ulanish baribir xato:", err)
        return 1
    print(f"Tayyor: baza '{db}' va foydalanuvchi '{user}' yaratildi, .env yangilandi.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nBekor qilindi.")
        sys.exit(1)
