; Inno Setup script for the albums Windows installer. The 0.0.0 version
; values are placeholders so this file is directly compilable;
; scripts/render_iss.py renders build/albums.iss from it with the real
; versions (the same directory depth keeps the relative paths below valid).

[Setup]
; unique and stable, so upgrades and uninstalls find earlier installs
AppId={{d03e11ba-65f7-48f2-a94f-4fabbd041213}
AppName=albums
AppVersion=0.0.0
AppVerName=albums 0.0.0
AppPublisher=4levity
AppPublisherURL=https://github.com/4levity/albums
AppSupportURL=https://github.com/4levity/albums/issues
AppUpdatesURL=https://github.com/4levity/albums/releases
VersionInfoVersion=0.0.0.0
MinVersion=10.0
DefaultDirName={autopf}\albums
DefaultGroupName=albums
DisableProgramGroupPage=yes
; per-user install (%LOCALAPPDATA%\Programs\albums), no elevation
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=albums_win_x86_64-0.0.0.0-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\pyinstaller\win_amd64\albums\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\albums"; Filename: "{app}\albums.exe"
Name: "{autodesktop}\albums"; Filename: "{app}\albums.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\albums.exe"; Description: "{cm:LaunchProgram,albums}"; Flags: nowait postinstall skipifsilent
