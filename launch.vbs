Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)

venvPython = appDir & "\.venv\Scripts\pythonw.exe"
runPy = appDir & "\run.py"

If fso.FileExists(venvPython) Then
    cmd = chr(34) & venvPython & chr(34) & " " & chr(34) & runPy & chr(34)
Else
    cmd = chr(34) & "pythonw.exe" & chr(34) & " " & chr(34) & runPy & chr(34)
End If

WshShell.CurrentDirectory = appDir
WshShell.Run cmd, 0, False
