# Zoom Platform

O'qituvchilar Telegram botda "Boshlash" tugmasini bosadi, bot har 40 daqiqalik blok uchun alohida Zoom yig'ilish yaratib, havolani yuboradi. Keyingi havola oldingi blok tugashiga 1 daqiqa qolganda **boshqa Zoom akkauntda** yaratiladi. Boshqaruv: React admin panel (LAN orqali).

**Stack:** Python 3.14, FastAPI, aiogram 3, SQLAlchemy 2 + MySQL, React (Vite + TypeScript).

## Qanday ishlaydi

1. O'qituvchi botda blok sonini tanlaydi, "Boshlash" bosadi.
2. Tizim barcha bloklar uchun Zoom akkauntlarni **oldindan band qiladi** (parallel darslar bir-birining akkauntini olmaydi). Yetarli bo'sh akkaunt bo'lmasa, dars boshlanmaydi va o'qituvchiga aytiladi.
3. 1-blok darhol yaratiladi. N-blok `(N-1)*40 daq - 60 sek` da yaratiladi va yuboriladi.
4. Bir darsda akkauntlar navbatlashadi: 1-blok A, 2-blok B, 3-blok yana A (A bo'shagach). Shuning uchun **bitta parallel dars uchun 2 ta akkaunt** kerak. 5 ta parallel dars = 10 ta, zaxira bilan 12–15 ta.
5. Akkaunt xato bersa (kalit, limit), tizim avtomatik boshqasiga o'tadi va adminni Telegram'da ogohlantiradi. Xato akkauntlar har 10 daqiqada qayta tekshiriladi.
6. Hamma rejalashtirilgan ishlar MySQL'da saqlanadi: kompyuter qayta yonsa, tizim qolgan joyidan davom etadi.

## O'rnatish (Windows)

Talablar: Python 3.14, Node.js 20+, MySQL (ishlab turibdi).

1. MySQL'da baza yarating:
   ```sql
   CREATE DATABASE zoomplatform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'zoom'@'localhost' IDENTIFIED BY 'KUCHLI_PAROL';
   GRANT ALL ON zoomplatform.* TO 'zoom'@'localhost';
   ```
2. PowerShell'da:
   ```powershell
   cd "C:\Zoom Platform"
   .\deploy\setup.ps1
   ```
   Skript virtual muhit yaratadi, kutubxonalarni o'rnatadi, frontendni build qiladi va `backend\.env` yaratib, sirlarni (`JWT_SECRET`, `FERNET_KEY`) chiqaradi.
3. `backend\.env` ni to'ldiring: `DATABASE_URL`, `BOT_TOKEN` (@BotFather), `ADMIN_TELEGRAM_IDS`, sirlar.
   > `FERNET_KEY` ni **yo'qotmang**: Zoom kalitlari shu bilan shifrlangan.
4. Birinchi admin: `backend\.venv\Scripts\python.exe backend\scripts\create_admin.py admin`
5. Sinov: `deploy\run_dev.bat`, so'ng brauzerda http://localhost:8000
6. Doimiy ishlash + `http://zoom.atko` (Administrator PowerShell): `.\deploy\install_local.ps1`, batafsil: `deploy\LOCAL.md`
7. Boshqa qurilmalar uchun routerda doimiy IP va `zoom.atko` DNS yozuvi (`deploy\LOCAL.md`).

Kompyuter uyqu rejimiga tushmasligi kerak: Sozlamalar → Quvvat → "Uyqu: hech qachon".

## Zoom akkaunt qo'shish

Har bir Zoom akkaunt uchun: https://marketplace.zoom.us → Develop → Build App → **Server-to-Server OAuth**.

- Scopes: `meeting:write:meeting:admin`, `meeting:delete:meeting:admin`, `user:read:user:admin` (yoki klassik `meeting:write:admin`, `meeting:delete:admin`, `user:read:admin`)
- Ilovani **Activate** qiling.
- Admin panel → Zoom akkauntlar → Qo'shish: nom, akkaunt egasining Zoom emaili, Account ID, Client ID, Client Secret → **Tekshirish**.

> Bepul (Basic) akkauntda S2S OAuth va meeting yaratish API'si ishlashini birinchi akkaunt bilan tekshirib ko'ring. Zoom foydalanish shartlari va API limitlari o'zgarib turadi.

## O'qituvchilarni qo'shish

Admin panel → O'qituvchilar → Qo'shish. Telegram ID **yoki** @username kiriting. O'qituvchi botga `/start` bosadi; ro'yxatda bo'lmasa bot unga ID raqamini ko'rsatadi, uni adminga yuboradi.

## Bot

- O'qituvchi: `▶️ Dars boshlash`, `📍 Joriy dars`, `📊 Statistikam`; dars paytida `⏭ Keyingisini hozir`, `➕ +1 blok`, `⏹ To'xtatish`.
- Admin (`ADMIN_TELEGRAM_IDS`): `/faol` (kim dars o'tayapti), `/akkauntlar`; xato ogohlantirishlari va oylik hisobot (har oyning 1-kuni).

## Sozlamalar (`.env`)

`BLOCK_MINUTES=40`, `LEAD_SECONDS=60` (keyingi havola necha soniya oldin), `MAX_BLOCKS=10`, `ACCOUNT_BUFFER_MINUTES=3` (akkaunt bo'shagandan keyingi zaxira), `TIMEZONE=Asia/Tashkent`.

## Xavfsizlik (LAN)

HTTPS yo'q, shuning uchun: kuchli admin paroli, login urinishlari cheklangan (15 daqiqada 5 ta), firewall faqat Private tarmoq. Internetga ochmang; kerak bo'lsa Cloudflare Tunnel qo'shing.

## Dasturlash

```
cd backend; .venv\Scripts\python -m pytest      # testlar
cd frontend; npm run dev                         # http://localhost:5173 (API 8000 ga proksi)
```

Loglar: `backend\logs\app.log`.
