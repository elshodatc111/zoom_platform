# install_local.ps1 o'rnatganini olib tashlaydi. ADMINISTRATOR PowerShell'da ishga tushiring.
param([string]$Domain = "zoom.atko", [int]$WebPort = 80)
$ErrorActionPreference = "Continue"
$nssm = (Get-Command nssm -ErrorAction SilentlyContinue).Source
if (-not $nssm) {
    $f = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter nssm.exe -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match "win64" } | Select-Object -First 1
    if ($f) { $nssm = $f.FullName }
}
if (-not $nssm) { throw "nssm topilmadi." }
foreach ($s in @("ZoomPlatform", "LocalProxy")) {
    if (Get-Service $s -ErrorAction SilentlyContinue) { & $nssm stop $s | Out-Null; & $nssm remove $s confirm | Out-Null }
}
Remove-NetFirewallRule -DisplayName "Zoom Platform Web ($WebPort)" -ErrorAction SilentlyContinue
$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
(Get-Content $hosts) | Where-Object { $_ -notmatch "\s$([regex]::Escape($Domain))(\s|$)" } | Set-Content $hosts -Encoding ASCII
Write-Host "Olib tashlandi. C:\ProgramData\LocalProxy papkasi (Caddy) qoldirildi: kerak bo'lmasa o'zingiz o'chiring."
