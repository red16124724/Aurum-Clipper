<#
  build_portable.ps1  —  ClipForge v1 portable-ZIP builder (Windows, GPU + CPU)

  Isko Haris (tum) apne is PC par ek dafa chalao. Yeh ek self-contained folder
  banata hai jismein sab kuch hota hai — embeddable Python, saari Python libraries
  (GPU CUDA libs samet), ffmpeg.exe, aur pre-downloaded whisper 'medium' model —
  phir usko ek .zip bana deta hai. Community wala bas extract karke Start.bat
  double-click karega. Koi install nahi. Card hua to Auto par GPU khud select.

  Run:
    cd "<repo>\ai-video-clipper"
    powershell -ExecutionPolicy Bypass -File packaging\build_portable.ps1

  Options:
    -PyVersion 3.11.9    (embeddable Python version to bundle)
    -Model medium        (whisper model to pre-bundle: base|small|medium)
    -OutDir ..\dist_portable
    -SkipZip             (folder bana do, .zip mat banao)
#>

[CmdletBinding()]
param(
  [string]$PyVersion = "3.11.9",
  [ValidateSet("base", "small", "medium", "large-v3")]
  [string]$Model = "medium",
  [string]$OutDir = "",
  [switch]$SkipZip
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest bahut tez ho jata hai

function Say($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }

# --- Paths -----------------------------------------------------------------
$RepoRoot = Split-Path -Parent $PSScriptRoot          # ...\ai-video-clipper
$AppDir   = Join-Path $RepoRoot "app"
$WebDist  = Join-Path $RepoRoot "web\dist"
$Assets   = Join-Path $RepoRoot "assets"
$Reqs     = Join-Path $RepoRoot "requirements.txt"

if (-not $OutDir) { $OutDir = Join-Path (Split-Path -Parent $RepoRoot) "dist_portable" }
$Bundle = Join-Path $OutDir "ClipForge"
$PyDir  = Join-Path $Bundle "python"
$FfDir  = Join-Path $Bundle "ffmpeg"
$Models = Join-Path $Bundle "models"

# --- Pre-flight ------------------------------------------------------------
Say "Pre-flight checks"
if (-not (Test-Path (Join-Path $WebDist "index.html"))) {
  throw "web\dist nahi mila. Pehle: cd web ; npm run build"
}
foreach ($p in @($AppDir, $Assets, $Reqs)) {
  if (-not (Test-Path $p)) { throw "Nahi mila: $p" }
}
$ttf = Get-ChildItem -Path (Join-Path $Assets "fonts") -Filter *.ttf -ErrorAction SilentlyContinue
if (-not $ttf) { Warn "assets\fonts mein koi .ttf nahi — app pehli run par fonts download karega (internet chahiye). Pehle app ek dafa chala ke fonts la lo taake offline bundle bane." }

if (Test-Path $Bundle) { Say "Purana bundle hata rahe hain"; Remove-Item $Bundle -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Bundle, $PyDir, $FfDir, $Models | Out-Null

# --- 1) Embeddable Python --------------------------------------------------
Say "Embeddable Python $PyVersion download + extract"
$pyZip = Join-Path $env:TEMP "python-embed-$PyVersion.zip"
$pyUrl = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip"
Invoke-WebRequest -Uri $pyUrl -OutFile $pyZip
Expand-Archive -Path $pyZip -DestinationPath $PyDir -Force

# ._pth ko edit karo taake `import site` on ho (pip + site-packages ke liye zaroori)
$pth = Get-ChildItem -Path $PyDir -Filter "python*._pth" | Select-Object -First 1
(Get-Content $pth.FullName) `
  | ForEach-Object { $_ -replace '^\s*#\s*import site\s*$', 'import site' } `
  | Set-Content $pth.FullName -Encoding Ascii
if (-not (Select-String -Path $pth.FullName -Pattern '^import site' -Quiet)) {
  Add-Content -Path $pth.FullName -Value "import site" -Encoding Ascii
}

$Py = Join-Path $PyDir "python.exe"

# --- 2) pip bootstrap ------------------------------------------------------
Say "pip install (get-pip)"
$getpip = Join-Path $env:TEMP "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
& $Py $getpip --no-warn-script-location
& $Py -m pip install --upgrade pip --no-warn-script-location

# --- 3) App dependencies + GPU (CUDA) stack --------------------------------
Say "App dependencies install (yeh sabse lamba step hai)"
& $Py -m pip install --no-warn-script-location -r $Reqs

Say "GPU (CUDA) libraries install — card walon ke liye"
# Yeh wo exact versions hain jo is machine ke venv par verify hue. Inhi se
# ctranslate2 GPU path chalta hai; inke bina sirf CPU chalega.
& $Py -m pip install --no-warn-script-location `
  "faster-whisper==1.2.1" `
  "ctranslate2==4.8.0" `
  "nvidia-cublas-cu12==12.9.2.10" `
  "nvidia-cuda-nvrtc-cu12==12.9.86" `
  "nvidia-cudnn-cu12==9.23.2.1"

# pip cache/temp bloat thora saaf
& $Py -m pip cache purge 2>$null

# --- 4) App code + assets + built frontend ---------------------------------
Say "app / assets / web\dist copy"
Copy-Item $AppDir   (Join-Path $Bundle "app")    -Recurse -Force
Copy-Item $Assets   (Join-Path $Bundle "assets") -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $Bundle "web") | Out-Null
Copy-Item $WebDist  (Join-Path $Bundle "web\dist") -Recurse -Force
Copy-Item $Reqs     (Join-Path $Bundle "requirements.txt") -Force
if (Test-Path (Join-Path $RepoRoot "README.md")) {
  Copy-Item (Join-Path $RepoRoot "README.md") (Join-Path $Bundle "README.md") -Force
}
# __pycache__ hata do
Get-ChildItem -Path (Join-Path $Bundle "app") -Recurse -Directory -Filter "__pycache__" |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# --- 5) ffmpeg (static build) ----------------------------------------------
Say "ffmpeg download + extract"
$ffZip = Join-Path $env:TEMP "ffmpeg-release.zip"
Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $ffZip
$ffTmp = Join-Path $env:TEMP "ffmpeg_extract"
if (Test-Path $ffTmp) { Remove-Item $ffTmp -Recurse -Force }
Expand-Archive -Path $ffZip -DestinationPath $ffTmp -Force
$ffExe = Get-ChildItem -Path $ffTmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
$ffProbe = Get-ChildItem -Path $ffTmp -Recurse -Filter "ffprobe.exe" | Select-Object -First 1
Copy-Item $ffExe.FullName (Join-Path $FfDir "ffmpeg.exe") -Force
if ($ffProbe) { Copy-Item $ffProbe.FullName (Join-Path $FfDir "ffprobe.exe") -Force }

# --- 6) Pre-bundle the whisper model (offline first run) -------------------
Say "Whisper '$Model' model pre-download (HF_HOME = bundle\models)"
$env:HF_HOME = $Models
$env:HF_HUB_DISABLE_TELEMETRY = "1"
$dl = @"
from faster_whisper import WhisperModel
# CPU/int8 par sirf download trigger karne ke liye load karte hain; files
# HF_HOME (bundle\models) mein cache ho jaati hain aur GPU/CPU dono use karenge.
WhisperModel('$Model', device='cpu', compute_type='int8')
print('model ready')
"@
$dlFile = Join-Path $env:TEMP "dl_model.py"
Set-Content -Path $dlFile -Value $dl -Encoding Ascii
& $Py $dlFile

# --- 7) Start.bat (end-user launcher) --------------------------------------
Say "Start.bat likh rahe hain"
$startBat = @'
@echo off
REM ===== ClipForge — double-click to run (koi install nahi) =====
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"

REM Bundled ffmpeg + python ko PATH par lao
set "PATH=%ROOT%ffmpeg;%ROOT%python;%PATH%"

REM Bundled whisper model use karo (offline — download ki koshish nahi)
set "HF_HOME=%ROOT%models"
set "HF_HUB_OFFLINE=1"
set "HF_HUB_DISABLE_TELEMETRY=1"

echo.
echo   ClipForge shuru ho rahi hai... browser khud khul jayega.
echo   Band karne ke liye is window ko close kar dein.
echo.

REM 5 sec baad browser khol do (tab tak server ready ho jata hai)
start "" cmd /c "timeout /t 5 >nul & start "" http://127.0.0.1:8000"

"%ROOT%python\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo   Server band ho gaya. Koi bhi key dabayen...
pause >nul
'@
Set-Content -Path (Join-Path $Bundle "Start.bat") -Value $startBat -Encoding Ascii

# --- 8) End-user README ----------------------------------------------------
$userReadme = @'
ClipForge — v1 (Portable)
=========================

Chalane ka tareeqa:
  1) Is folder ko kahin bhi extract karein (Desktop theek hai).
  2) "Start.bat" par double-click karein.
  3) Browser khud http://127.0.0.1:8000 par khul jayega. Bas.

Kuch install karne ki zarurat NAHI — Python, ffmpeg, model sab andar hai.
100% aapke PC par chalti hai; koi API key nahi.

GPU (graphics card):
  - Agar aapke paas NVIDIA card hai to app "Compute" par "Auto" hone se
    khud GPU use karegi (bahut tez). Card na ho to CPU par chalegi (thodi slow).

Zaruri:
  - Windows 10/11 (64-bit).
  - Video URL se clip banane ke liye internet chahiye (yt-dlp video laata hai).
    Apni file upload karke offline bhi chala sakte hain.

Masla aaye to:
  - Antivirus/SmartScreen rok de to "More info -> Run anyway".
  - "VCRUNTIME140.dll missing" jaisa error aaye to Microsoft Visual C++
    Redistributable (x64) install kar lein, phir dobara Start.bat.
  - Port 8000 busy ho to koi aur ClipForge/uvicorn pehle se chal raha hoga.

Banaya: The Haris — 100% local pipeline (yt-dlp - faster-whisper - ffmpeg)
'@
Set-Content -Path (Join-Path $Bundle "READ ME FIRST.txt") -Value $userReadme -Encoding Ascii

# --- 9) Zip ----------------------------------------------------------------
$sizeGB = "{0:N2}" -f ((Get-ChildItem $Bundle -Recurse | Measure-Object Length -Sum).Sum / 1GB)
Say "Bundle taiyaar: $Bundle  (~$sizeGB GB)"

if ($SkipZip) { Say "SkipZip — .zip nahi banaya. Folder ready hai."; return }

$zipPath = Join-Path $OutDir "ClipForge-v1-portable.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$sevenZip = (Get-Command 7z.exe -ErrorAction SilentlyContinue).Source
if ($sevenZip) {
  Say "7-Zip se compress kar rahe hain (bade folder ke liye behtar)"
  & $sevenZip a -tzip -mx=5 "$zipPath" "$Bundle" | Out-Null
} else {
  Warn "7-Zip nahi mila — Compress-Archive use kar rahe hain (4GB+ par slow/na-mumkin ho sakta hai)."
  Warn "Behtar: 7-Zip install karke folder ko khud zip karein, ya -SkipZip de kar folder hi share karein."
  Compress-Archive -Path (Join-Path $Bundle '*') -DestinationPath $zipPath -CompressionLevel Optimal
}

if (Test-Path $zipPath) {
  $zGB = "{0:N2}" -f ((Get-Item $zipPath).Length / 1GB)
  Say "HO GAYA -> $zipPath  (~$zGB GB)"
}
