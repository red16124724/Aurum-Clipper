<#
  Launch.ps1 — starts the bundled server hidden (no console window) and opens
  the browser once it's actually ready. Run via ClipForge.vbs so even this
  PowerShell window never flashes on screen — double-click should feel like
  opening a normal desktop app, not a script.
#>
$ErrorActionPreference = "SilentlyContinue"
$Root = $PSScriptRoot

$env:PATH = "$Root\ffmpeg;$Root\python;$env:PATH"
$env:HF_HOME = "$Root\models"
$env:HF_HUB_DISABLE_TELEMETRY = "1"
# No HF_HUB_OFFLINE here on purpose: the whisper model is NOT pre-bundled (it
# alone is ~1.5GB, over GitHub's 2GB release-asset limit) — huggingface_hub
# downloads it into $Root\models on first launch and reuses that cache on
# every launch after. Everything else (Python, pip deps, CUDA libs, ffmpeg)
# IS bundled, since that was the actual source of "no git/node/python"
# install failures, not the model.

$py = Join-Path $Root "python\python.exe"
Start-Process -FilePath $py `
  -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
  -WorkingDirectory $Root -WindowStyle Hidden

# Poll /health instead of a blind sleep, so the browser opens the moment the
# server is actually ready. Generous timeout on first run specifically: the
# server doesn't start accepting requests until the whisper model finishes
# downloading + loading, which can take a few minutes on a slow connection.
$ready = $false
for ($i = 0; $i -lt 600; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $ready = $true; break }
  } catch {}
  Start-Sleep -Seconds 1
}

Start-Process "http://127.0.0.1:8000"

if (-not $ready) {
  # Still open the tab — most of the wait is the whisper model warming up on
  # first launch, and the page itself shows a "Connecting..." state until then.
}
