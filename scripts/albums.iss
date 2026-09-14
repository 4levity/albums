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

[Files]
Source: "..\dist\pyinstaller\win_amd64\albums\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\albums"; Filename: "{app}\albums.exe"

[Code]
// Add {app} to the user's PATH, remove when uninstalled.
const
  InstallerRegSubkey = 'Software\4levity\albums';

// Trim, unquote, strip trailing backslashes and expand a PATH entry so that
// entries compare consistently.
function CleanPathEntry(AEntry: String): String;
begin
  Result := Trim(AEntry);
  if (Length(Result) >= 2) and (Result[1] = '"') and (Result[Length(Result)] = '"') then
  begin
    Delete(Result, 1, 1);
    Delete(Result, Length(Result), 1);
  end;
  while (Length(Result) > 1) and (Result[Length(Result)] = '\') do
    Delete(Result, Length(Result), 1);
  Result := ExpandConstant(Result);
end;

function IsAppDirInUserPath(AAppDir: String): Boolean;
var
  Path, Entry: String;
  SemicolonPos: Integer;
begin
  Result := False;
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Path) then
    Exit;
  while Path <> '' do
  begin
    SemicolonPos := Pos(';', Path);
    if SemicolonPos = 0 then
    begin
      Entry := Path;
      Path := '';
    end
    else
    begin
      Entry := Copy(Path, 1, SemicolonPos - 1);
      Path := Copy(Path, SemicolonPos + 1, Length(Path) - SemicolonPos);
    end;
    if SameText(CleanPathEntry(Entry), AAppDir) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

procedure AddAppDirToUserPath(AAppDir: String);
var
  Path: String;
begin
  Path := '';
  if RegQueryStringValue(HKCU, 'Environment', 'Path', Path)
    and (Path <> '')
    and (Path[Length(Path)] <> ';')
  then
    Path := Path + ';';
  RegWriteStringValue(HKCU, 'Environment', 'Path', Path + AAppDir);
end;

procedure RemoveAppDirFromUserPath(AAppDir: String);
var
  Path, NewPath, Entry: String;
  SemicolonPos: Integer;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Path) then
    Exit;
  NewPath := '';
  while Path <> '' do
  begin
    SemicolonPos := Pos(';', Path);
    if SemicolonPos = 0 then
    begin
      Entry := Path;
      Path := '';
    end
    else
    begin
      Entry := Copy(Path, 1, SemicolonPos - 1);
      Path := Copy(Path, SemicolonPos + 1, Length(Path) - SemicolonPos);
    end;
    if not SameText(CleanPathEntry(Entry), AAppDir) then
    begin
      if NewPath <> '' then
        NewPath := NewPath + ';';
      NewPath := NewPath + Entry;
    end;
  end;
  RegWriteStringValue(HKCU, 'Environment', 'Path', NewPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  AppDir := ExpandConstant('{app}');
  if IsAppDirInUserPath(AppDir) then
    Exit;
  AddAppDirToUserPath(AppDir);
  RegWriteStringValue(HKCU, InstallerRegSubkey, 'AddedToUserPath', 'yes');
  SuppressibleMsgBox(
    'albums was installed to:'#13#10 +
    '  ' + AppDir + #13#10#13#10 +
    'It was added to your user PATH.' + #13#10 +
    'Log out and log back in, then open a terminal and run: albums',
    mbInformation, MB_OK, IDOK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AddedToUserPath: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  if RegQueryStringValue(HKCU, InstallerRegSubkey, 'AddedToUserPath', AddedToUserPath) then
    RemoveAppDirFromUserPath(ExpandConstant('{app}'));
  RegDeleteValue(HKCU, InstallerRegSubkey, 'AddedToUserPath');
  RegDeleteKeyIfEmpty(HKCU, InstallerRegSubkey);
end;
