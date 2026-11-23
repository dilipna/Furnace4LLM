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
UninstallDisplayIcon={app}\runtime\pythonw.exe
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
Name: "{userprograms}\Furnace"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m furnace_api.desktop"; WorkingDir: "{app}"
Name: "{userdesktop}\Furnace"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m furnace_api.desktop"; WorkingDir: "{app}"; Tasks: desktopicon
[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: "-I -m furnace_api.desktop"; Description: "Open Furnace"; Flags: postinstall nowait skipifsilent
[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Code: Integer;
begin
  if (CurUninstallStep = usUninstall) and not UninstallSilent then begin
    MsgBox('Close the Furnace window first. Your workspace, model files and exports are kept by default.', mbInformation, MB_OK);
    if MsgBox('Remove containers and networks owned by the default Furnace workspace? Docker must be running. Model weights and images will be kept.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      if not Exec(ExpandConstant('{app}\runtime\python.exe'), '-I -m furnace.cli studio-cleanup --workspace "' + ExpandConstant('{userprofile}\.furnace\studio') + '" --yes', '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
        MsgBox('Cleanup could not be confirmed. Workspace and model files are retained. See the cleanup guide before removing data.', mbInformation, MB_OK);
    { Data is deliberately never deleted by the installer. Users review retention
      and perform optional deletion in the documented cleanup flow. }
  end;
end;
