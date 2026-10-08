> **Eslatma:** Alwaysdata bepul tarifida Services yo'q va dastur bo'sh turganda to'xtatiladi, shuning uchun bu usul
> bot va dars rejalovchi uchun ishonchsiz. Tavsiya: kompyuterda doimiy ishlatish, qarang `LOCAL.md`.

# Alwaysdata.com'ga GitHub'dan o'rnatish

Bot va dars rejalovchi **doimiy ishlashi** kerak (har 40 daqiqada havola yaratadi). Shuning uchun dastur
oddiy "Python sayt" sifatida emas, **Service** (doimiy ishlaydigan jarayon) sifatida ishga tushiriladi,
sayt esa unga **Reverse proxy** orqali ulanadi.

> `frontend/dist` (tayyor admin panel) GitHub'ga kiritilgan, serverda Node/npm kerak emas.
> Frontendni o'zgartirsangiz: kompyuterda `cd frontend && npm run build`, so'ng `git add -A && git commit && git push`.

## 1. GitHub'ga yuklash (kompyuterda, bir marta)

```powershell
cd "C:\Zoom Platform"
git init
git add -A
git commit -m "Zoom Platform: mobil dizayn"
git branch -M main
git remote add origin https://github.com/<LOGIN>/zoom-platform.git
git push -u origin main
```
Repo **private** bo'lsin (kodda sirlar yo'q, lekin baribir). `.env` va `.venv` `.gitignore` orqali chiqmaydi.

## 2. Alwaysdata panelida baza

1. **Databases → MySQL → Add a database**: nom `zoom` (to'liq nomi `HISOB_zoom` bo'ladi).
2. **Users → MySQL → Add a user** va uni bazaga to'liq huquq bilan biriktiring.
3. Server manzili: `mysql-HISOB.alwaysdata.net`.

## 3. Serverga kod olish (SSH)

Alwaysdata: **Remote access → SSH** yoqing, keyin:
```bash
ssh HISOB@ssh-HISOB.alwaysdata.net
git clone https://github.com/<LOGIN>/zoom-platform.git ~/zoom-platform
cd ~/zoom-platform/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python scripts/gen_secrets.py     # chiqqan JWT_SECRET va FERNET_KEY ni .env ga qo'ying
nano .env
```
Private repo bo'lsa, `git clone` uchun GitHub **Personal Access Token** (yoki deploy key) kerak.

`.env` da to'ldiring:
```
DATABASE_URL=mysql+aiomysql://HISOB_foydalanuvchi:PAROL@mysql-HISOB.alwaysdata.net:3306/HISOB_zoom
BOT_TOKEN=...
ADMIN_TELEGRAM_IDS=...
JWT_SECRET=...
FERNET_KEY=...          # yo'qotmang: Zoom kalitlari shu bilan shifrlanadi
COOKIE_SECURE=true
HOST=127.0.0.1
PORT=8100
```
Birinchi admin:
```bash
.venv/bin/python scripts/create_admin.py admin
```

## 4. Doimiy jarayon (Service)

**Advanced → Services → Add a service**:

- Command: `/home/HISOB/zoom-platform/backend/.venv/bin/python run.py`
- Working directory: `/home/HISOB/zoom-platform/backend`
- Environment: bo'sh qoldiring (hammasi `.env` da)

Saqlang va ishga tushiring. Loglar: `~/zoom-platform/backend/logs/app.log`.

## 5. Sayt (Reverse proxy)

**Web → Sites → Add a site**:

- Addresses: `HISOB.alwaysdata.net` (yoki o'z domeningiz)
- Type: **Reverse proxy**
- Target: `http://127.0.0.1:8100` (`.env` dagi `PORT` bilan bir xil)

Brauzerda `https://HISOB.alwaysdata.net` ni oching.

## 6. Yangilash

```bash
ssh HISOB@ssh-HISOB.alwaysdata.net
bash ~/zoom-platform/deploy/alwaysdata_update.sh
```
So'ng panelda Services → Restart.

## Eslatmalar

- Bepul tarifda resurslar cheklangan (disk/RAM/MySQL hajmi). Tarifingizda **Services** borligini panelda tekshiring;
  bo'lmasa, "User program" saytini va Site → Advanced → *Idle timeout = 0* ni sinab ko'ring, lekin
  Alwaysdata uni baribir to'xtatishi mumkin, bunda bot va rejalovchi to'xtaydi.
- Kompyuter (Windows) bilan bir vaqtda **bir xil BOT_TOKEN** bilan ishlatmang: Telegram bitta botga faqat bitta
  ishlovchi jarayonga ruxsat beradi. Serverga o'tgach, kompyuterdagi xizmatni o'chiring.
- Bazani ko'chirmoqchi bo'lsangiz: eski MySQL'dan `mysqldump`, yangisiga import.
