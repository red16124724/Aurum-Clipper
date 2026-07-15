<#
  run.ps1 — ClipForge one-file installer + launcher (GitHub par rehta hai)

  ClipForge.bat isko GitHub se download karke chalati hai. Yeh pehli baar sab kuch
  KHUD download karta hai (portable Python, saari libraries + GPU CUDA, ffmpeg),
  phir app chalata hai. Model + fonts app khud pehli transcription/run par le aata
  hai. Dobara chalane par (kuch already maujood) seedha launch — fast.

  Sab kuch usi folder mein install hota hai jahan ClipForge.bat rakhi hai.
  Card (NVIDIA) hua to app "Auto" par khud GPU use karti hai, warna CPU.
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# --- Config ----------------------------------------------------------------
$PyVer  = "3.11.9"
$Repo   = "Ai-Haris/clipping-tool"
$Branch = "main"
$ZipUrl = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"

$Base = $PSScriptRoot                      # jahan ClipForge.bat + run.ps1 hai
Set-Location $Base
$Py = Join-Path $Base "python\python.exe"

function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  ClipForge — setup & launch" -ForegroundColor Magenta
Write-Host "  Install folder: $Base"
Write-Host ""

# --- 1) Portable Python (agar nahi hai) ------------------------------------
if (-not (Test-Path $Py)) {
  Say "Portable Python $PyVer download (~10 MB)..."
  $z = Join-Path $env:TEMP "cf_py.zip"
  Invoke-WebRequest -UseBasicParsing "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $z
  Expand-Archive $z (Join-Path $Base "python") -Force
  # `import site` on karo taake pip aur libraries chalein
  $pth = Get-ChildItem (Join-Path $Base "python") -Filter "python*._pth" | Select-Object -First 1
  (Get-Content $pth.FullName) -replace '^\s*#\s*import site\s*$', 'import site' | Set-Content $pth.FullName -Encoding Ascii
  if (-not (Select-String -Path $pth.FullName -Pattern '^import site' -Quiet)) {
    Add-Content $pth.FullName "import site" -Encoding Ascii
  }
  Say "pip bootstrap..."
  $gp = Join-Path $env:TEMP "cf_getpip.py"
  Invoke-WebRequest -UseBasicParsing "https://bootstrap.pypa.io/get-pip.py" -OutFile $gp
  & $Py $gp --no-warn-script-location
}

# --- 2) App code GitHub se (har run par latest; fail ho to purana chalao) ---
try {
  Say "App code GitHub se laa rahe hain..."
  $z = Join-Path $env:TEMP "cf_app.zip"
  Invoke-WebRequest -UseBasicParsing $ZipUrl -OutFile $z
  $ex = Join-Path $env:TEMP "cf_app"; if (Test-Path $ex) { Remove-Item $ex -Recurse -Force }
  Expand-Archive $z $ex -Force
  $src = Get-ChildItem $ex -Directory | Select-Object -First 1     # clipping-tool-main
  foreach ($d in @("app", "assets", "web", "requirements.txt", "README.md")) {
    $s = Join-Path $src.FullName $d
    if (Test-Path $s) { Copy-Item $s $Base -Recurse -Force }
  }
} catch {
  if (Test-Path (Join-Path $Base "app\main.py")) { Warn "GitHub se update na ho saka — pehle wala code use kar rahe hain." }
  else { throw }
}

if (-not (Test-Path (Join-Path $Base "web\dist\index.html"))) {
  Warn "web\dist missing — GitHub par built frontend commit hona chahiye (packaging guide dekhein)."
}

# --- 3) Libraries (ek dafa; marker se re-run fast) -------------------------
$marker = Join-Path $Base ".deps_ok"
if (-not (Test-Path $marker)) {
  Say "Libraries install ho rahi hain — ek dafa ka kaam, thoda internet + waqt lagega..."
  & $Py -m pip install --no-warn-script-location -r (Join-Path $Base "requirements.txt")
  Say "GPU (CUDA) libraries — card walon ke liye..."
  & $Py -m pip install --no-warn-script-location `
      "faster-whisper==1.2.1" "ctranslate2==4.8.0" `
      "nvidia-cublas-cu12==12.9.2.10" "nvidia-cuda-nvrtc-cu12==12.9.86" "nvidia-cudnn-cu12==9.23.2.1"
  "ok" | Out-File $marker -Encoding Ascii
  Say "Libraries ready."
}

# --- 4) ffmpeg (agar nahi hai) ---------------------------------------------
if (-not (Test-Path (Join-Path $Base "ffmpeg\ffmpeg.exe"))) {
  Say "ffmpeg download..."
  $z = Join-Path $env:TEMP "cf_ff.zip"
  Invoke-WebRequest -UseBasicParsing "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $z
  $fx = Join-Path $env:TEMP "cf_ff"; if (Test-Path $fx) { Remove-Item $fx -Recurse -Force }
  Expand-Archive $z $fx -Force
  New-Item -ItemType Directory -Force (Join-Path $Base "ffmpeg") | Out-Null
  Copy-Item (Get-ChildItem $fx -Recurse -Filter ffmpeg.exe  | Select-Object -First 1).FullName (Join-Path $Base "ffmpeg\ffmpeg.exe") -Force
  $fp = Get-ChildItem $fx -Recurse -Filter ffprobe.exe | Select-Object -First 1
  if ($fp) { Copy-Item $fp.FullName (Join-Path $Base "ffmpeg\ffprobe.exe") -Force }
}

# --- 5) Launch -------------------------------------------------------------
$env:PATH = (Join-Path $Base "ffmpeg") + ";" + (Join-Path $Base "python") + ";" + $env:PATH
$env:HF_HOME = Join-Path $Base "models"          # whisper model yahin cache hoga
$env:HF_HUB_DISABLE_TELEMETRY = "1"

Write-Host ""
Say "ClipForge chal rahi hai..."
Write-Host "  Browser khud http://127.0.0.1:8000 par khulega."
Write-Host "  PEHLI BAAR: whisper model (~1.5 GB) download hoga — 'Connecting...' dikhe to sabar karein."
Write-Host "  Band karne ke liye is window ko close kar dein."
Write-Host ""

Start-Process "cmd" -ArgumentList '/c timeout /t 6 >nul & start "" http://127.0.0.1:8000' -WindowStyle Hidden
& $Py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
