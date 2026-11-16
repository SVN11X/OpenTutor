; Inno Setup script. Per-user install, no administrator rights, a normal uninstaller.
; Build: scripts\build-installer.ps1
#define AppVersion "0.5.0"

[Setup]
AppId={{B6F0D1B2-6C0E-4B1E-9C55-0F1A5E2C7A11}
AppName=OpenTutor Guardian
AppVersion={#AppVersion}
AppPublisher=SVN11X
AppPublisherURL=https://github.com/SVN11X/OpenTutor
DefaultDirName={localappdata}\Programs\OpenTutorGuardian
DefaultGroupName=OpenTutor Guardian
PrivilegesRequired=lowest
OutputDir=..\..\dist\installer
OutputBaseFilename=OpenTutorGuardian-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\OpenTutorGuardian.exe
LicenseFile=..\..\LICENSE
SetupIconFile=..\..\src\guardian\assets\guardian.ico

[Files]
Source: "..\..\dist\OpenTutorGuardian\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\OpenTutor Guardian"; Filename: "{app}\OpenTutorGuardian.exe"
Name: "{group}\Uninstall OpenTutor Guardian"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\OpenTutorGuardian.exe"; Description: "Start OpenTutor Guardian"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v OpenTutorGuardian /f"; Flags: runhidden; RunOnceId: "RemoveAutostart"
