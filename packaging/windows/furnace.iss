#ifndef AppVersion
  #error Build through scripts/build_windows.py
#endif
[Setup]
AppId={{3F41BE5E-54F7-4D62-A03C-187CB6478E72}
AppName=Furnace
AppVersion={#AppVersion}
AppPublisher=Furnace4LLM
DefaultDirName={localappdata}\Programs\Furnace
DefaultGroupName=Furnace
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#Output}
OutputBaseFilename=Furnace-{#AppVersion}-{#Copy(SourceCommit, 1, 12)}-windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Furnace
UninstallDisplayIcon={app}\furnace.ico
SetupIconFile={#SourcePath}furnace.ico
CloseApplications=yes
RestartApplications=no
#ifdef SignBuild
SignTool=furnace
SignedUninstaller=yes
#endif
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: checkedonce
[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{group}\Furnace"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m furnace_api.desktop"; WorkingDir: "{app}"; IconFilename: "{app}\furnace.ico"
Name: "{userdesktop}\Furnace"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m furnace_api.desktop"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\furnace.ico"
[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m furnace_api.desktop"; Description: "Open Furnace"; Flags: postinstall nowait skipifsilent
[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Code: Integer; Options: String;
begin
  if (CurUninstallStep = usUninstall) and not UninstallSilent then begin
    MsgBox('Close the Furnace window first. Your workspace, model files and exports are kept by default.', mbInformation, MB_OK);
    if MsgBox('Remove containers and networks owned by the default Furnace workspace? Docker must be running.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then begin
      Options := '';
      if MsgBox('Also remove verified weights in the default workspace and pinned Docker images? Custom model folders and external stores are kept.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then Options := Options + ' --weights';
      if MsgBox('Also remove saved project records, evaluations and operation logs from the default workspace? Project folders and exported files are kept.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then Options := Options + ' --records';
      if not Exec(ExpandConstant('{app}\runtime\python.exe'), '-I -m furnace_api.desktop_cleanup' + Options, '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
        MsgBox('Optional cleanup did not complete. Retained data needs manual review. See the cleanup guide.', mbInformation, MB_OK);
    end;
  end;
end;
