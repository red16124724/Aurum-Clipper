; Aurum Clipper - Windows installer (Inno Setup)
; Made by RED4724
;
; Packages the self-contained portable bundle (built by build_portable.ps1 -
; embedded Python, CUDA libs, ffmpeg, and the pre-downloaded whisper model)
; behind a normal Windows installer: Start Menu/Desktop shortcuts, an
; uninstaller, and a hidden-console launcher so it opens like a real desktop
; app instead of a visible script window.
;
; Installs per-user (no admin, no UAC prompt) because the app writes its own
; data (downloads/, clips/, transcripts/, models/) as siblings of its own
; folder - that requires a writable install location, which Program Files
; is not for a standard user.
;
; Build:
;   "C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" packaging\AurumClipper.iss

#define MyAppName "Aurum Clipper"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "RED4724"
#define MyAppURL "https://github.com/red16124724/aurum-clipper"
#define BundleDir "..\..\dist_portable\AurumClipper"

[Setup]
AppId={{8F2B6C1A-4E3D-4A7B-9C5E-2D1F7A6B9E10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} Beta (Made by {#MyAppPublisher})
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist_installer
OutputBaseFilename=AurumClipper-Setup-v{#MyAppVersion}-beta
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=AurumClipper.ico
UninstallDisplayIcon={app}\AurumClipper.ico
DisableWelcomePage=no
ChangesEnvironment=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Launch.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "AurumClipper.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "Stop Aurum Clipper.vbs"; DestDir: "{app}"; DestName: "Stop Aurum Clipper.vbs"; Flags: ignoreversion
Source: "AurumClipper.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\AurumClipper.vbs"; WorkingDir: "{app}"; IconFilename: "{app}\AurumClipper.ico"
Name: "{group}\Stop {#MyAppName}"; Filename: "{app}\Stop Aurum Clipper.vbs"; WorkingDir: "{app}"; IconFilename: "{app}\AurumClipper.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\AurumClipper.vbs"; WorkingDir: "{app}"; IconFilename: "{app}\AurumClipper.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\AurumClipper.vbs"; Description: "Launch {#MyAppName} now"; Flags: postinstall nowait skipifsilent shellexec

[UninstallDelete]
; Recursive catch-all, not per-folder: Python leaves __pycache__/*.pyc behind
; after every run. This also covers downloads/clips/transcripts/models cache growth.
Type: filesandordirs; Name: "{app}"

[Code]
// Warn before uninstalling that clips/downloads live inside the app folder
// and will be removed too, since that's not obvious for a portable-style app.
function InitializeUninstall(): Boolean;
begin
  Result := MsgBox('Uninstalling Aurum Clipper (Made by RED4724) will also delete any downloaded videos and generated clips stored inside its folder. Continue?',
    mbConfirmation, MB_YESNO) = idYes;
end;
