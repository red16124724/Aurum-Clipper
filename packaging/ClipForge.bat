@echo off
REM =====================================================================
REM  ClipForge — bas is file par double-click karein.
REM  Pehli baar sab kuch (Python, libraries, ffmpeg, model) KHUD download
REM  hota hai isi folder mein. Baad ki dafa seedha khul jata hai.
REM  Kuch alag install karne ki zarurat NAHI.
REM =====================================================================
setlocal
cd /d "%~dp0"

echo.
echo   ClipForge shuru ho rahi hai... (pehli baar setup mein waqt lagega)
echo.

REM Latest launcher GitHub se lao
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/Ai-Haris/clipping-tool/main/packaging/run.ps1' -OutFile 'run.ps1'"
if not exist "run.ps1" (
  echo.
  echo   Launcher download nahi ho saka. Internet check karein aur dobara chalayein.
  echo.
  pause
  exit /b 1
)

REM Installer + app chalao
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"

echo.
echo   ClipForge band ho gayi. Is window ko close kar sakte hain.
pause >nul
