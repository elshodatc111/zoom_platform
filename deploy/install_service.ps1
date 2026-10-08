# Windows xizmati sifatida o'rnatish (kompyuter yoqilganda avtomatik ishga tushadi).
# ADMINISTRATOR sifatida ishga tushiring. NSSM kerak: https://nssm.cc  (yoki: winget install NSSM.NSSM)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\backend\.venv\Scripts\python.exe"
$name = "ZoomPlatform"

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) { throw "nssm topilmadi. 'winget install NSSM.NSSM' bilan o'rnating." }
if (-not (Test-Path $py)) { throw "Avval deploy\setup.ps1 ni ishga tushiring." }

nssm install $name $py "run.py"
nssm set $name AppDirectory "$root\backend"
nssm set $name Start SERVICE_AUTO_START
nssm set $name AppExit Default Restart
nssm set $name AppRestartDelay 5000
nssm set $name AppStdout "$root\backend\logs\service.out.log"
nssm set $name AppStderr "$root\backend\logs\service.err.log"
nssm set $name AppRotateFiles 1
nssm set $name AppRotateBytes 5000000
New-Item -ItemType Directory -Force "$root\backend\logs" | Out-Null

# MySQL xizmati ishga tushgandan keyin boshlansin (xizmat nomi boshqacha bo'lsa o'zgartiring: MySQL80)
if (Get-Service "MySQL80" -ErrorAction SilentlyContinue) { nssm set $name DependOnService MySQL80 }

nssm start $name
Write-Host "Xizmat o'rnatildi va ishga tushdi. Holat: nssm status $name"
