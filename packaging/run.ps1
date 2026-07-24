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
function Step($n, $total, $label, $already) {
  Write-Host ""
  if ($already) { Write-Host "[$n/$total] $label -- already installed, skipping" -ForegroundColor DarkGray }
  else { Write-Host "[$n/$total] $label -- downloading now..." -ForegroundColor Green }
}

# Downloads WITH a real, visible progress bar (% + speed) — plain
# Invoke-WebRequest with $ProgressPreference=SilentlyContinue shows nothing
# on screen for a big file, which looks exactly like a frozen/stuck window.
# Retries once on failure (GitHub/codeload can be slow or blip) before giving
# up with a clear message instead of hanging silently forever.
function Get-FileWithProgress($Url, $OutFile, $Label) {
  for ($attempt = 1; $attempt -le 2; $attempt++) {
    try {
      Write-Host "    Downloading $Label ..." -ForegroundColor DarkCyan
      $prev = $ProgressPreference
      $ProgressPreference = "Continue"
      Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $OutFile -TimeoutSec 180
      $ProgressPreference = $prev
      return
    } catch {
      $ProgressPreference = $prev
      if ($attempt -ge 2) {
        Warn "Could not download $Label after 2 tries: $($_.Exception.Message)"
        Warn "Check your internet connection and run ClipForge.bat again."
        throw
      }
      Warn "$Label download failed once, retrying in 3s..."
      Start-Sleep -Seconds 3
    }
  }
}

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Magenta
Write-Host "   ClipForge  --  by Haris AI" -ForegroundColor Magenta
Write-Host "   100% local video clipper -- setup & launch" -ForegroundColor Magenta
Write-Host "  ============================================" -ForegroundColor Magenta
Write-Host "  Install folder: $Base"
Write-Host ""

$TOTAL_STEPS = 5

# --- 1) Portable Python (agar nahi hai) ------------------------------------
Step 1 $TOTAL_STEPS "Python (portable runtime)" (Test-Path $Py)
if (-not (Test-Path $Py)) {
  Say "Portable Python $PyVer download (~10 MB)..."
  $z = Join-Path $env:TEMP "cf_py.zip"
  Get-FileWithProgress "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" $z "Python $PyVer"
  Expand-Archive $z (Join-Path $Base "python") -Force
  # `import site` on karo taake pip aur libraries chalein
  $pth = Get-ChildItem (Join-Path $Base "python") -Filter "python*._pth" | Select-Object -First 1
  (Get-Content $pth.FullName) -replace '^\s*#\s*import site\s*$', 'import site' | Set-Content $pth.FullName -Encoding Ascii
  if (-not (Select-String -Path $pth.FullName -Pattern '^import site' -Quiet)) {
    Add-Content $pth.FullName "import site" -Encoding Ascii
  }
  Say "pip bootstrap..."
  $gp = Join-Path $env:TEMP "cf_getpip.py"
  Get-FileWithProgress "https://bootstrap.pypa.io/get-pip.py" $gp "pip installer"
  & $Py $gp --no-warn-script-location
}

# --- 2) App code GitHub se (har run par latest; fail ho to purana chalao) ---
Step 2 $TOTAL_STEPS "ClipForge app code (latest from GitHub)" $false
try {
  Say "App code GitHub se laa rahe hain (~50 MB, dhyan se progress dekhein neeche)..."
  $z = Join-Path $env:TEMP "cf_app.zip"
  Get-FileWithProgress $ZipUrl $z "ClipForge app code"
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
Step 3 $TOTAL_STEPS "Python libraries + GPU (CUDA) support" (Test-Path $marker)
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
Step 4 $TOTAL_STEPS "ffmpeg" (Test-Path (Join-Path $Base "ffmpeg\ffmpeg.exe"))
if (-not (Test-Path (Join-Path $Base "ffmpeg\ffmpeg.exe"))) {
  Say "ffmpeg download..."
  $z = Join-Path $env:TEMP "cf_ff.zip"
  Get-FileWithProgress "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $z "ffmpeg"
  $fx = Join-Path $env:TEMP "cf_ff"; if (Test-Path $fx) { Remove-Item $fx -Recurse -Force }
  Expand-Archive $z $fx -Force
  New-Item -ItemType Directory -Force (Join-Path $Base "ffmpeg") | Out-Null
  Copy-Item (Get-ChildItem $fx -Recurse -Filter ffmpeg.exe  | Select-Object -First 1).FullName (Join-Path $Base "ffmpeg\ffmpeg.exe") -Force
  $fp = Get-ChildItem $fx -Recurse -Filter ffprobe.exe | Select-Object -First 1
  if ($fp) { Copy-Item $fp.FullName (Join-Path $Base "ffmpeg\ffprobe.exe") -Force }
}

# --- 5) Launch -------------------------------------------------------------
Step 5 $TOTAL_STEPS "Starting ClipForge" $false
$env:PATH = (Join-Path $Base "ffmpeg") + ";" + (Join-Path $Base "python") + ";" + $env:PATH
$env:HF_HOME = Join-Path $Base "models"          # whisper model yahin cache hoga
$env:HF_HUB_DISABLE_TELEMETRY = "1"

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Magenta
Write-Host "   ClipForge by Haris AI -- ready" -ForegroundColor Magenta
Write-Host "  ============================================" -ForegroundColor Magenta
Write-Host "  Browser khud http://127.0.0.1:8000 par khulega."
Write-Host "  PEHLI BAAR: whisper model app ke andar hi download + progress bar ke saath dikhega."
Write-Host "  Band karne ke liye is window ko close kar dein."
Write-Host ""

Start-Process "cmd" -ArgumentList '/c timeout /t 6 >nul & start "" http://127.0.0.1:8000' -WindowStyle Hidden
& $Py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
