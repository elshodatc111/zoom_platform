# LAN orqali kirish uchun faqat PRIVATE tarmoqda 8000-portni ochadi. ADMINISTRATOR sifatida ishga tushiring.
param([int]$Port = 8000)
New-NetFirewallRule -DisplayName "Zoom Platform Admin ($Port)" -Direction Inbound -Protocol TCP `
    -LocalPort $Port -Action Allow -Profile Private
Write-Host "Port $Port private tarmoq uchun ochildi."
Write-Host "Kompyuter IP manzili:"
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" } | Select-Object IPAddress, InterfaceAlias
Write-Host "Boshqa qurilmadan: http://<IP>:$Port  (routerda ushbu kompyuterga doimiy IP bering!)"
