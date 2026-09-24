@echo off
echo Installing Aurum Clipper...
set VBS="%temp%\CreateShortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %VBS%
echo sLinkFile = "%USERPROFILE%\Desktop\Aurum Clipper.lnk" >> %VBS%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %VBS%
echo oLink.TargetPath = "%~dp0Aurum Clipper.exe" >> %VBS%
echo oLink.WorkingDirectory = "%~dp0" >> %VBS%
echo oLink.IconLocation = "shell32.dll,116" >> %VBS%
echo oLink.Save >> %VBS%
cscript /nologo %VBS%
del %VBS%
echo Installation Complete! An Aurum Clipper shortcut has been placed on your Desktop.
pause
