# Zoom Platform: shu kompyuterda doimiy ishlash (Windows xizmati) + http://zoom.atko
#
# ADMINISTRATOR PowerShell'da:
#   cd "C:\Zoom Platform"
#   Set-ExecutionPolicy -Scope Process Bypass -Force
#   .\deploy\install_local.ps1
#
# Nima qiladi:
#   1. Dasturni 127.0.0.1:8765 da (faqat shu kompyuterdan) eshitadigan qiladi: boshqa loyihalar portiga tegmaydi.
#   2. "ZoomPlatform" xizmatini yaratadi: kompyuter yonganda, hech kim tizimga kirmasa ham, o'zi ishga tushadi.
#   3. "LocalProxy" (Caddy) xizmatini yaratadi: 80-portda domen nomi bo'yicha yo'naltiradi (zoom.atko -> 8765).
#      Boshqa loyiha qo'shish: C:\ProgramData\LocalProxy\sites\ ichiga yangi .caddy fayl qo'ying.
#   4. hosts faylga domen yozadi va firewallda 80-portni faqat Private tarmoq uchun ochadi.
param(
    [string]$Domain = "zoom.atko",
    [int]$AppPort = 8765,
    [int]$WebPort = 80
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
$envFile = Join-Path $root "backend\.env"
$proxyDir = "C:\ProgramData\LocalProxy"
$caddyExe = Join-Path $proxyDir "caddy.exe"
$appSvc = "ZoomPlatform"
$proxySvc = "LocalProxy"

function Step($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }

# ---------- 0. Tekshiruvlar
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "PowerShell'ni 'Administrator sifatida ishga tushirish' bilan oching." }
if (-not (Test-Path $py)) { throw "Python muhiti topilmadi: $py. Avval deploy\setup.ps1 ni ishga tushiring." }
if (-not (Test-Path $envFile)) { throw "backend\.env topilmadi." }

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

# ---------- 1. NSSM (xizmat o'rnatuvchi)
Step "NSSM tekshirilmoqda"
Refresh-Path
if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id NSSM.NSSM -e --accept-source-agreements --accept-package-agreements | Out-Null
        Refresh-Path
    }
}
$nssm = (Get-Command nssm -ErrorAction SilentlyContinue).Source
if (-not $nssm) {
    $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter nssm.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "win64" } | Select-Object -First 1
    if ($found) { $nssm = $found.FullName }
}
if (-not $nssm) { throw "NSSM o'rnatilmadi. Qo'lda: 'winget install NSSM.NSSM', so'ng PowerShell'ni yopib qayta oching." }
Write-Host "NSSM: $nssm"

# ---------- 2. Eski xizmatlarni to'xtatish (qayta ishga tushirish xavfsiz bo'lishi uchun)
foreach ($s in @($appSvc, $proxySvc)) {
    if (Get-Service $s -ErrorAction SilentlyContinue) {
        & $nssm stop $s 2>&1 | Out-Null
        & $nssm remove $s confirm 2>&1 | Out-Null
    }
}
Start-Sleep -Seconds 2

# ---------- 3. Portlar band emasligini tekshirish
function Test-PortFree($port, $label) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        throw "$label porti ($port) band: $($p.ProcessName) (PID $($c.OwningProcess)). Uni to'xtating yoki boshqa port bering."
    }
}
Step "Portlar tekshirilmoqda"
Test-PortFree $AppPort "Dastur"
Test-PortFree $WebPort "Veb (proksi)"
Write-Host "Portlar bo'sh."

# ---------- 4. .env: faqat shu kompyuterdan eshitadigan, noyob port
Step ".env yangilanmoqda (nusxasi: .env.bak)"
Copy-Item $envFile "$envFile.bak" -Force
$lines = [System.Collections.Generic.List[string]]([IO.File]::ReadAllLines($envFile))
function Set-EnvValue($key, $value) {
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$key\s*=") { $lines[$i] = "$key=$value"; $found = $true }
    }
    if (-not $found) { $lines.Add("$key=$value") }
}
Set-EnvValue "HOST" "127.0.0.1"
Set-EnvValue "PORT" "$AppPort"
Set-EnvValue "COOKIE_SECURE" "false"
[IO.File]::WriteAllLines($envFile, $lines, (New-Object System.Text.UTF8Encoding $false))

# ---------- 5. Caddy
Step "Caddy (proksi) tayyorlanmoqda"
New-Item -ItemType Directory -Force $proxyDir, "$proxyDir\sites", "$proxyDir\logs" | Out-Null
if (-not (Test-Path $caddyExe)) {
    Write-Host "caddy.exe yuklab olinmoqda..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "https://caddyserver.com/api/download?os=windows&arch=amd64" -OutFile $caddyExe -UseBasicParsing
}
& $caddyExe version
if ($LASTEXITCODE -ne 0) { throw "caddy.exe ishlamadi. Faylni o'chirib, skriptni qayta ishga tushiring: $caddyExe" }

$mainCfg = Join-Path $proxyDir "Caddyfile"
if (-not (Test-Path $mainCfg)) {
    $main = @"
{
	admin off
	auto_https off
}

import sites/*.caddy
"@
    [IO.File]::WriteAllText($mainCfg, $main, (New-Object System.Text.UTF8Encoding $false))
}
$site = @"
http://$Domain {
	encode gzip
	reverse_proxy 127.0.0.1:$AppPort
}
"@
[IO.File]::WriteAllText("$proxyDir\sites\zoom.caddy", $site, (New-Object System.Text.UTF8Encoding $false))
& $caddyExe validate --config $mainCfg --adapter caddyfile
if ($LASTEXITCODE -ne 0) { throw "Caddyfile xato. Fayllarni tekshiring: $proxyDir\sites" }

# ---------- 6. Xizmatlar
Step "Xizmatlar o'rnatilmoqda"
New-Item -ItemType Directory -Force (Join-Path $root "backend\logs") | Out-Null
$mysql = Get-Service | Where-Object { $_.Name -match "^(MySQL|MariaDB)" } | Select-Object -First 1

& $nssm install $appSvc $py "run.py" | Out-Null
& $nssm set $appSvc AppDirectory (Join-Path $root "backend") | Out-Null
& $nssm set $appSvc DisplayName "Zoom Platform" | Out-Null
& $nssm set $appSvc Start SERVICE_DELAYED_AUTO_START | Out-Null
& $nssm set $appSvc AppEnvironmentExtra "PYTHONUTF8=1" | Out-Null
& $nssm set $appSvc AppExit Default Restart | Out-Null
& $nssm set $appSvc AppRestartDelay 5000 | Out-Null
& $nssm set $appSvc AppStdout (Join-Path $root "backend\logs\service.out.log") | Out-Null
& $nssm set $appSvc AppStderr (Join-Path $root "backend\logs\service.err.log") | Out-Null
& $nssm set $appSvc AppRotateFiles 1 | Out-Null
& $nssm set $appSvc AppRotateBytes 5000000 | Out-Null
if ($mysql) { & $nssm set $appSvc DependOnService $mysql.Name | Out-Null; Write-Host "MySQL xizmati: $($mysql.Name) (undan keyin ishga tushadi)" }
else { Write-Host "MySQL xizmati topilmadi: dastur baribir ishga tushadi va ulanguncha qayta urinadi." -ForegroundColor Yellow }

& $nssm install $proxySvc $caddyExe "run" "--config" $mainCfg "--adapter" "caddyfile" | Out-Null
& $nssm set $proxySvc AppDirectory $proxyDir | Out-Null
& $nssm set $proxySvc DisplayName "Local Proxy (Caddy)" | Out-Null
& $nssm set $proxySvc Start SERVICE_DELAYED_AUTO_START | Out-Null
& $nssm set $proxySvc AppExit Default Restart | Out-Null
& $nssm set $proxySvc AppRestartDelay 5000 | Out-Null
& $nssm set $proxySvc AppStdout "$proxyDir\logs\caddy.out.log" | Out-Null
& $nssm set $proxySvc AppStderr "$proxyDir\logs\caddy.err.log" | Out-Null
& $nssm set $proxySvc AppRotateFiles 1 | Out-Null
& $nssm set $proxySvc AppRotateBytes 5000000 | Out-Null

# ---------- 7. hosts va firewall
Step "hosts va firewall"
$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
if (-not (Select-String -Path $hosts -Pattern "\s$([regex]::Escape($Domain))(\s|$)" -Quiet)) {
    Add-Content -Path $hosts -Value "127.0.0.1`t$Domain" -Encoding ASCII
    Write-Host "hosts: 127.0.0.1 $Domain"
}
foreach ($n in @("Zoom Platform Web ($WebPort)", "Zoom Platform Admin (8000)")) {
    Remove-NetFirewallRule -DisplayName $n -ErrorAction SilentlyContinue
}
New-NetFirewallRule -DisplayName "Zoom Platform Web ($WebPort)" -Direction Inbound -Protocol TCP `
    -LocalPort $WebPort -Action Allow -Profile Private | Out-Null
Write-Host "Firewall: $WebPort-port faqat Private tarmoq uchun ochildi."
powercfg /change standby-timeout-ac 0 | Out-Null
Write-Host "Quvvat: tarmoqdan ishlaganda uyqu rejimi o'chirildi."

# ---------- 8. Ishga tushirish va tekshirish
Step "Ishga tushirilmoqda"
& $nssm start $appSvc | Out-Null
& $nssm start $proxySvc | Out-Null
$ok = $false
for ($i = 0; $i -lt 40 -and -not $ok; $i++) {
    Start-Sleep -Seconds 2
    try { $ok = (Invoke-RestMethod "http://$Domain/api/health" -TimeoutSec 3).ok } catch { $ok = $false }
}
Write-Host ""
if ($ok) { Write-Host "TAYYOR: http://$Domain ishlayapti." -ForegroundColor Green }
else {
    Write-Host "Sayt hali javob bermadi. Loglarni ko'ring:" -ForegroundColor Yellow
    Write-Host "  $root\backend\logs\service.err.log"
    Write-Host "  $root\backend\logs\app.log"
}

$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -match "^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)" } | Select-Object -ExpandProperty IPAddress
Write-Host ""
Write-Host "Boshqa qurilmalar (telefon, noutbuk) uchun:" -ForegroundColor Cyan
Write-Host "  Kompyuter IP manzili: $($ips -join ', ')"
Write-Host "  1) Routerda shu kompyuterga doimiy IP bering (DHCP reservation)."
Write-Host "  2) Routerning DNS bo'limida $Domain -> shu IP yozuvini qo'shing."
Write-Host "     Router buni qo'llamasa, har qurilmada hosts/DNS qo'lda sozlanadi (deploy\LOCAL.md)."
