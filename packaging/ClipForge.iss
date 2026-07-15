; ClipForge — Windows installer (Inno Setup)
;
; Packages the self-contained portable bundle (built by build_portable.ps1 —
; embedded Python, CUDA libs, ffmpeg, and the pre-downloaded whisper model)
; behind a normal Windows installer: Start Menu/Desktop shortcuts, an
; uninstaller, and a hidden-console launcher so it opens like a real desktop
; app instead of a visible script window.
;
; Installs per-user (no admin, no UAC prompt) because the app writes its own
; data (downloads/, clips/, transcripts/, models/) as siblings of its own
; folder — that requires a writable install location, which Program Files
; is not for a standard user.
;
; Build:
;   "C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" packaging\ClipForge.iss

#define MyAppName "ClipForge"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "The Haris"
#define MyAppURL "https://github.com/Ai-Haris/clipping-tool"
#define BundleDir "..\..\dist_portable\ClipForge"

[Setup]
AppId={{8F2B6C1A-4E3D-4A7B-9C5E-2D1F7A6B9E10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} Beta
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist_installer
OutputBaseFilename=ClipForge-Setup-v{#MyAppVersion}-beta
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=ClipForge.ico
UninstallDisplayIcon={app}\ClipForge.ico
DisableWelcomePage=no
ChangesEnvironment=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Launch.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "ClipForge.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "Stop ClipForge.vbs"; DestDir: "{app}"; DestName: "Stop ClipForge.vbs"; Flags: ignoreversion
Source: "ClipForge.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\ClipForge.vbs"; WorkingDir: "{app}"; IconFilename: "{app}\ClipForge.ico"
Name: "{group}\Stop {#MyAppName}"; Filename: "{app}\Stop ClipForge.vbs"; WorkingDir: "{app}"; IconFilename: "{app}\ClipForge.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\ClipForge.vbs"; WorkingDir: "{app}"; IconFilename: "{app}\ClipForge.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\ClipForge.vbs"; Description: "Launch {#MyAppName} now"; Flags: postinstall nowait skipifsilent shellexec

[UninstallDelete]
; Recursive catch-all, not per-folder: Python leaves __pycache__/*.pyc behind
; after every run (confirmed in testing — Inno only tracks files IT installed,
; so runtime-generated files like these block a plain directory removal with
; "not empty" otherwise). This also covers downloads/clips/transcripts/models
; cache growth without needing to enumerate every runtime-created path by name.
Type: filesandordirs; Name: "{app}"

[Code]
// Warn before uninstalling that clips/downloads live inside the app folder
// and will be removed too, since that's not obvious for a portable-style app.
function InitializeUninstall(): Boolean;
begin
  Result := MsgBox('Uninstalling ClipForge will also delete any downloaded videos and generated clips stored inside its folder (your whisper model cache and settings included). Continue?',
    mbConfirmation, MB_YESNO) = idYes;
end;
