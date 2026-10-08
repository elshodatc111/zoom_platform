# Shu kompyuterda doimiy ishlatish (http://zoom.atko)

Dastur Windows xizmati sifatida kompyuter yonishi bilan o'zi ishga tushadi (hech kim tizimga kirmasa ham).
Boshqa loyihalarga xalaqit bermasligi uchun:

- Dastur faqat `127.0.0.1:8765` da eshitadi (8000 kabi mashhur port emas), tashqaridan to'g'ridan-to'g'ri ko'rinmaydi.
- 80-portda kichik proksi (Caddy, "LocalProxy" xizmati) domen nomiga qarab yo'naltiradi: `zoom.atko` -> 8765.
- Alohida Python muhiti (`backend\.venv`) va alohida baza.

## O'rnatish (bir marta)

1. Alwaysdata'dagi nusxani **to'xtating** (Web -> Sites -> saytni o'chiring). Bitta bot tokeni bilan faqat bitta nusxa ishlaydi.
2. Kompyuterda `run.bat` yoki `run_dev.bat` ochiq bo'lsa, yoping.
3. PowerShell'ni **Administrator** sifatida oching:
   ```powershell
   cd "C:\Zoom Platform"
   Set-ExecutionPolicy -Scope Process Bypass -Force
   .\deploy\install_local.ps1
   ```
4. Oxirida `TAYYOR: http://zoom.atko ishlayapti.` chiqsa, shu kompyuterda brauzerda `http://zoom.atko` ni oching.

80-port band bo'lsa (masalan, XAMPP/IIS/nginx), skript to'xtab, kim band qilganini aytadi. Shunda boshqa loyihaning
domenini ham shu proksiga qo'shing (pastga qarang) yoki menga ayting.

## Boshqa qurilmalarda (telefon, noutbuk) `zoom.atko` ochilishi

Brauzer `zoom.atko` ni kompyuter IP manziliga aylantirishi kerak (DNS).

1. Routerda shu kompyuterga **doimiy IP** bering (DHCP reservation / "Static lease"), masalan `192.168.1.50`.
2. Routerning **Local DNS / DNS Host Mapping / Static DNS** bo'limida `zoom.atko -> 192.168.1.50` yozuvini qo'shing.
   Shunda barcha qurilmalarda avtomatik ishlaydi.
3. Router buni qo'llamasa: har qurilmada qo'lda.
   - Windows: `C:\Windows\System32\drivers\etc\hosts` ga `192.168.1.50 zoom.atko` qo'shing (Administrator).
   - macOS/Linux: `/etc/hosts` ga shu qatorni qo'shing.
   - Android/iPhone: hosts yo'q, shuning uchun router DNS yozuvi kerak (yoki `http://192.168.1.50`).
4. `.atko` rasmiy domen emas, faqat sizning tarmog'ingizda ishlaydi. Qurilmada "Private DNS" yoki VPN yoqilgan bo'lsa,
   u local DNS ni chetlab o'tishi mumkin.

## Boshqa loyiha qo'shish (xalaqit bermasdan)

`C:\ProgramData\LocalProxy\sites\` ichiga yangi fayl yarating, masalan `crm.caddy`:
```
http://crm.atko {
	reverse_proxy 127.0.0.1:5000
}
```
Keyin: `Restart-Service LocalProxy`. Zoom Platform fayliga (`zoom.caddy`) tegmang.
Boshqa loyiha o'z portida (masalan 5000) ishlayversin, 8765 ni ishlatmang.

## Kundalik buyruqlar (Administrator PowerShell)

```powershell
Get-Service ZoomPlatform, LocalProxy            # holat
Restart-Service ZoomPlatform                    # dasturni qayta ishga tushirish (yangilangandan keyin)
Get-Content "C:\Zoom Platform\backend\logs\app.log" -Tail 50 -Wait   # jonli log
```
Yangilash: yangi kod fayllarini qo'ying (kerak bo'lsa `cd frontend; npm run build`), keyin `Restart-Service ZoomPlatform`.

## Olib tashlash

`.\deploy\uninstall_local.ps1` (Administrator).

## Xavfsizlik

- Port faqat **Private** tarmoq uchun ochiladi. Internetga ochmang.
- HTTPS yo'q, shuning uchun kuchli admin paroli qo'ying.
- Baza uchun `root` o'rniga alohida foydalanuvchi ishlating (README'dagi `CREATE USER 'zoom'...` ga qarang).
