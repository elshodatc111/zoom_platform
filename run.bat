@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Zoom Platform
set "PY=%~dp0backend\.venv\Scripts\python.exe"

rem ---------- 1. Virtual muhit
if not exist "%PY%" (
  echo [1/5] Python virtual muhit yaratilmoqda...
  py -3.14 -m venv backend\.venv 2>nul
  if not exist "%PY%" py -3 -m venv backend\.venv
  if not exist "%PY%" (
    echo XATO: Python topilmadi. Python 3.14 ni python.org dan o'rnating ^(Add to PATH / py launcher bilan^).
    pause & exit /b 1
  )
)

rem ---------- 2. Kutubxonalar
if not exist "backend\.venv\.deps_ok" (
  echo [2/5] Python kutubxonalari o'rnatilmoqda...
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r backend\requirements.txt
  if errorlevel 1 ( echo XATO: kutubxonalar o'rnatilmadi. & pause & exit /b 1 )
  echo ok> backend\.venv\.deps_ok
)

rem ---------- 3. Admin panel build
if not exist "frontend\dist\index.html" (
  echo [3/5] Admin panel yig'ilmoqda ^(bir marta^)...
  pushd frontend
  call npm install --no-audit --no-fund
  call npm run build
  popd
  if not exist "frontend\dist\index.html" ( echo XATO: frontend build bo'lmadi. Node.js o'rnatilganini tekshiring. & pause & exit /b 1 )
)

rem ---------- 4. Sozlamalar (.env)
"%PY%" backend\scripts\init_env.py
if not exist "backend\.env_ok" (
  echo [4/5] Sozlamalar fayli tekshirilmoqda...
  echo.
  echo Ochilgan faylda DATABASE_URL, BOT_TOKEN va ADMIN_TELEGRAM_IDS ni to'ldiring,
  echo saqlang va Notepad ni yoping.
  notepad backend\.env
  echo ok> backend\.env_ok
)

rem ---------- MySQL tekshiruvi
"%PY%" backend\scripts\ensure_db.py
if errorlevel 1 (
  echo XATO: MySQL tayyor emas. backend\.env dagi DATABASE_URL ni tekshiring.
  pause & exit /b 1
)

rem ---------- 5. Birinchi admin
if not exist "backend\.admin_ok" (
  echo [5/5] Birinchi admin yaratilmoqda.
  set /p ADMIN_LOGIN=Admin login ^(masalan: admin^): 
  "%PY%" backend\scripts\create_admin.py !ADMIN_LOGIN!
  if errorlevel 1 ( pause & exit /b 1 )
  echo ok> backend\.admin_ok
)

rem ---------- Ishga tushirish
echo.
echo Zoom Platform ishga tushmoqda: http://localhost:8000
echo To'xtatish: Ctrl+C
cd backend
"%PY%" run.py
echo.
echo Dastur to'xtadi.
pause
