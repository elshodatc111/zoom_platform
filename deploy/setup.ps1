# Birinchi o'rnatish: PowerShell'ni oddiy rejimda ishga tushiring
#   cd "C:\Zoom Platform"; .\deploy\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== Python 3.14 tekshiruvi"
py -3.14 --version

Write-Host "== Virtual muhit va kutubxonalar"
if (-not (Test-Path "$root\backend\.venv")) { py -3.14 -m venv "$root\backend\.venv" }
& "$root\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$root\backend\.venv\Scripts\python.exe" -m pip install -r "$root\backend\requirements.txt"

Write-Host "== Frontend build"
Set-Location "$root\frontend"
npm install --no-audit --no-fund
npm run build
Set-Location $root

if (-not (Test-Path "$root\backend\.env")) {
    Copy-Item "$root\backend\.env.example" "$root\backend\.env"
    Write-Host ""
    Write-Host "== backend\.env yaratildi. Quyidagi sirlarni uning ichiga qo'ying:"
    & "$root\backend\.venv\Scripts\python.exe" "$root\backend\scripts\gen_secrets.py"
    Write-Host ""
    Write-Host "Keyin .env ichida DATABASE_URL, BOT_TOKEN, ADMIN_TELEGRAM_IDS ni to'ldiring."
}
Write-Host ""
Write-Host "Keyingi qadam: birinchi admin yaratish:"
Write-Host "  backend\.venv\Scripts\python.exe backend\scripts\create_admin.py admin"
