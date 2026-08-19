; Windows 7 SP1 64-bit installer for TXT News to Excel Sync.
;
; Built from dist-win7\WordToExcelHindiSync.exe (Python 3.8.10 + PyInstaller
; 5.13.2 - see WINDOWS_7_SETUP.md). Differs from installer.iss only in:
;   - sourcing the EXE from dist-win7\ instead of dist\
;   - silently chain-installing the official Microsoft Visual C++ 2015-2022
;     x64 Redistributable first if it isn't already present, which supplies
;     the Universal CRT (api-ms-win-crt-*.dll / ucrtbase.dll) that Windows 7
;     SP1 does not ship by default. This is the same officially-supported
;     redistributable Microsoft ships for every modern VC++/UCRT app; it is
;     freely redistributable and is NOT a random/unofficial DLL download.
#define MyAppName "TXT News to Excel Sync"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TXT News to Excel Sync"
#define MyAppExeName "WordToExcelHindiSync.exe"

[Setup]
AppId={{6A9F1D2E-8B3C-4A7D-9E1F-2C5B8A6D4F10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output_win7
OutputBaseFilename=WordToExcelHindiSync_Win7_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Windows 7 SP1 (build 7601) is the minimum supported OS for this build.
MinVersion=6.1sp1
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist-win7\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "win7_prereqs\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: VCRedistNeedsInstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Official Microsoft VC++ 2015-2022 x64 Redistributable - only runs if not
; already present (VCRedistNeedsInstall). Supplies the Universal CRT that
; Windows 7 SP1 lacks out of the box; this is the Microsoft-documented way
; to get api-ms-win-crt-*.dll / ucrtbase.dll onto Windows 7.
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ Runtime (required on Windows 7)..."; Check: VCRedistNeedsInstall; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function VCRedistNeedsInstall: Boolean;
var
  Installed: Cardinal;
begin
  // The VC++ 2015-2022 runtime installer writes this key on successful
  // install (x64 redistributable, 64-bit registry view). If it's already
  // there (e.g. from another app, or Windows Update), skip re-running it.
  if RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64', 'Installed', Installed) then
    Result := (Installed <> 1)
  else
    Result := True;
end;
