' Stop Aurum Clipper.vbs - Made by RED4724
' Gracefully stops the running local server.
Set shell = CreateObject("WScript.Shell")
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command " & _
  """Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | " & _
  "Select-Object -Expand OwningProcess -Unique | " & _
  "ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"""
shell.Run cmd, 0, True
MsgBox "Aurum Clipper has been stopped.", 64, "Aurum Clipper - Made by RED4724"
