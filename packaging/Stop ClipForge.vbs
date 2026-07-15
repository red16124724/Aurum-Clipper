' Stop ClipForge.vbs — closing the browser tab does not quit the app (the
' server keeps running so your edit isn't lost if you close the tab by
' accident). Use this shortcut to actually shut it down. Finds whatever
' process is listening on ClipForge's port and stops it — no PID bookkeeping
' needed, and it can't accidentally kill an unrelated app.
Set shell = CreateObject("WScript.Shell")
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command " & _
  """Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | " & _
  "Select-Object -Expand OwningProcess -Unique | " & _
  "ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"""
shell.Run cmd, 0, True
MsgBox "ClipForge has been stopped.", 64, "ClipForge"
