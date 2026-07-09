# ClipForge v1 — Community ke sath share karne ki guide

Faisla (locked): **Portable ZIP · GPU + CPU · whisper `medium`**. User kuch install
nahi karega — extract karke `Start.bat` double-click. Card hua to "Auto" par GPU khud
select ho jata hai (yeh app mein pehle se hai).

---

## 1) Build karo (ek dafa, apne is PC par)

```powershell
cd "e:\The Haris Hustle\Vibe code\Cliping\ai-video-clipper"

# frontend fresh build (agar UI mein koi change kiya ho)
cd web ; npm run build ; cd ..

# portable bundle + zip banao
powershell -ExecutionPolicy Bypass -File packaging\build_portable.ps1
```

Output: `..\dist_portable\ClipForge-v1-portable.zip` (~4 GB).
Andar: `python\`, `ffmpeg\`, `models\`, `app\`, `assets\`, `web\dist\`, `Start.bat`,
`READ ME FIRST.txt`.

> Tip: zip ke liye **7-Zip** install kar lo (`winget install 7zip.7zip`). 4GB folder
> ko Compress-Archive slow/na-mumkin kar deta hai; script 7-Zip ho to khud use kar leti hai.
> Ya `-SkipZip` de kar sirf folder banao aur khud 7-Zip se zip karo.

---

## 2) Build se pehle ek dafa test (apne PC par)

Zip banane se pehle folder khud verify kar lo:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_portable.ps1 -SkipZip
cd ..\dist_portable\ClipForge
.\Start.bat
```

Browser khule, ek chhoti video (URL ya upload) se 30s clip banao — GPU/CPU dono theek
chal rahe hain confirm karo. Phir asli zip bana lo.

---

## 3) Host kahan karo (download link)

| Jagah | Theek jab | Note |
|------|-----------|------|
| **GitHub Releases** | tumhara repo public/private hai | Har file ≤ 2 GB → 4GB ke liye zip ko `.001/.002` mein split karo (7-Zip: `-v1900m`) ya neeche wala use karo |
| **Google Drive / MEGA / Dropbox** | sabse aasan bade file ke liye | Public link banao; MEGA 4GB aaram se le leta hai |
| **Torrent (optional)** | bade audience, bandwidth bachani ho | qBittorrent se `.torrent` + magnet |

Recommended sabse aasan: **MEGA ya Google Drive** par 4GB zip, ek link community ko.

---

## 4) Community ko yeh message do

> **ClipForge v1 (Windows)** — kisi bhi video ko captioned vertical shorts bana do,
> 100% apne PC par, koi API key nahi.
> 1. Link se zip download karo → extract karo.
> 2. `Start.bat` double-click.
> 3. Browser khud khul jayega. Bas.
> NVIDIA card hai to khud tez (GPU) chalega, warna CPU par.
> Pehli baar SmartScreen roke to *More info → Run anyway*.

---

## 5) Aksar aane wale sawal / fixes (community ko bata dena)

- **SmartScreen / Antivirus warning** → `Start.bat` unsigned hai; *Run anyway*. (Aage
  chah kar code-signing certificate le sakte ho, v1 ke liye zaruri nahi.)
- **`VCRUNTIME140.dll` missing** → Microsoft Visual C++ Redistributable (x64) install.
- **Port 8000 busy** → koi aur ClipForge pehle se chal rahi hai; usko band karo.
- **GPU use nahi ho raha** → bahut purana/AMD card ya driver purana. App khud CPU par
  gir jati hai; kaam phir bhi hota hai, bas slow.

---

## 6) Aage v2 ke liye (abhi zaruri nahi)

- **Chhota "CPU-only" pack** (~1GB) un logon ke liye jinke paas card nahi — tez download.
  (`build_portable.ps1` mein GPU install step hata do.)
- **Code-signed installer** (Inno Setup) → SmartScreen warning khatam, Start Menu shortcut.
- **Auto-update check** → app start par latest version ping.
- **`WHISPER_MODEL` env** → user apna model size choose kar sake.

---

### Jo cheezein pehle se ho chuki hain
- Frontend build (`web/dist`) — end user ko Node nahi chahiye.
- GPU auto-detect + "Auto/GPU/CPU" selector — card hua to khud select.
- 100% local, koi cloud/API key nahi.
