Write-Host "Installing ClipForge AI Dependencies..." -ForegroundColor Cyan

# Install python dependencies
pip install -r requirements.txt
pip install pywebview

Write-Host "Creating shortcuts..." -ForegroundColor Cyan

$WshShell = New-Object -comObject WScript.Shell

# 1. Create a VBS script to launch without a console window
$vbsPath = "$PSScriptRoot\launch.vbs"
$vbsContent = "Set WshShell = CreateObject("WScript.Shell")
"
$vbsContent += "WshShell.Run chr(34) & "pythonw.exe" & chr(34) & " " & chr(34) & "$PSScriptRoot\run.py" & chr(34), 0, False"
Set-Content -Path $vbsPath -Value $vbsContent -Encoding Ascii

# 2. Desktop Shortcut
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcut = $WshShell.CreateShortcut("$desktop\ClipForge AI.lnk")
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = ""$vbsPath""
$shortcut.WorkingDirectory = "$PSScriptRoot"
$shortcut.IconLocation = "shell32.dll,116" # Video camera icon
$shortcut.Save()

# 3. Start Menu Shortcut
$startMenu = [Environment]::GetFolderPath('Programs')
$shortcutSM = $WshShell.CreateShortcut("$startMenu\ClipForge AI.lnk")
$shortcutSM.TargetPath = "wscript.exe"
$shortcutSM.Arguments = ""$vbsPath""
$shortcutSM.WorkingDirectory = "$PSScriptRoot"
$shortcutSM.IconLocation = "shell32.dll,116"
$shortcutSM.Save()

Write-Host "Installation Complete! You can now launch ClipForge AI from your Desktop or Start Menu." -ForegroundColor Green
Pause
