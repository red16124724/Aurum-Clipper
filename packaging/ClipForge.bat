@echo off
REM =====================================================================
REM  ClipForge by Haris AI — bas is file par double-click karein.
REM  Koi git/node/python pehle se install hona ZARURI NAHI — sab kuch
REM  (Python, libraries, ffmpeg, AI model) is file ke andar hi khud
REM  download ho jata hai, isi folder mein. Baad ki dafa seedha khul jata
REM  hai — dobara download nahi hota.
REM =====================================================================
setlocal
cd /d "%~dp0"

echo.
echo   ============================================
echo    ClipForge  --  by Haris AI
echo   ============================================
echo.
echo   Shuru ho rahi hai... (pehli baar setup mein 5-10 minute lag sakte hain)
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
