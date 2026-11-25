param([Parameter(Mandatory=$true)][string]$AppDir, [Parameter(Mandatory=$true)][string]$Installer, [Parameter(Mandatory=$true)][string]$Screenshots)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class FurnaceWindow {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public delegate bool WindowCallback(IntPtr hwnd, IntPtr data);
  [DllImport("user32.dll")] static extern bool EnumWindows(WindowCallback callback, IntPtr data);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint id);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd, System.Text.StringBuilder text, int count);
  public static IntPtr Find(int pid, string title) {
    IntPtr result=IntPtr.Zero;
    EnumWindows((hwnd, data) => {uint id; GetWindowThreadProcessId(hwnd,out id); var text=new System.Text.StringBuilder(256); GetWindowText(hwnd,text,256); if(id==pid && text.ToString().StartsWith(title)) {result=hwnd; return false;} return true;},IntPtr.Zero);
    return result;
  }
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out Rect rect);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hwnd, uint message, IntPtr wparam, IntPtr lparam);
  public struct Rect { public int Left, Top, Right, Bottom; }
}
'@
[FurnaceWindow]::SetProcessDPIAware() | Out-Null
function Save-Window($Process, $File, [IntPtr]$Handle) {
  $Process.Refresh()
  $rect = New-Object FurnaceWindow+Rect
  [FurnaceWindow]::GetWindowRect($Handle, [ref]$rect) | Out-Null
  if ($rect.Right - $rect.Left -lt 100) { throw 'No rendered application window' }
  $bitmap = New-Object System.Drawing.Bitmap(($rect.Right-$rect.Left), ($rect.Bottom-$rect.Top))
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $hdc = $graphics.GetHdc()
  try { if (-not [FurnaceWindow]::PrintWindow($Handle,$hdc,2)) { throw 'Window capture refused' } }
  finally { $graphics.ReleaseHdc($hdc); $graphics.Dispose() }
  $bitmap.Save($File,[System.Drawing.Imaging.ImageFormat]::Png)
  $bitmap.Dispose()
}
New-Item -ItemType Directory -Force -Path $Screenshots | Out-Null
$Screenshots = [IO.Path]::GetFullPath($Screenshots)
$startedAt = Get-Date
$wizard = Start-Process -FilePath $Installer -ArgumentList @('/SP-','/LANG=english') -WindowStyle Hidden -PassThru
$childIds = @()
try {
  $wizardWindow = $null
  for ($attempt=0; $attempt -lt 100; $attempt++) {
    $childIds = @($childIds + @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($wizard.Id)" | Select-Object -ExpandProperty ProcessId) | Select-Object -Unique)
    foreach ($candidate in @($wizard.Id) + $childIds) {
      $wizardHandle = [FurnaceWindow]::Find($candidate, 'Setup')
      if ($wizardHandle -ne [IntPtr]::Zero) { $wizardWindow = Get-Process -Id $candidate; break }
    }
    if ($wizardWindow) { break }
    Start-Sleep -Milliseconds 100
  }
  if (-not $wizardWindow) { throw 'Installer window did not open' }
  Save-Window $wizardWindow (Join-Path $Screenshots 'installer.png') $wizardHandle
} finally {
  # This is a welcome-page capture, before any install action. Only our new wizard is stopped.
  if ($wizardWindow -and -not $wizardWindow.HasExited) { Stop-Process -Id $wizardWindow.Id }
  foreach ($childId in $childIds) { Stop-Process -Id $childId -ErrorAction SilentlyContinue }
  if (-not $wizard.HasExited) { Stop-Process -Id $wizard.Id }
}
$testWorkspace = Join-Path ([IO.Path]::GetTempPath()) ('furnace-window-' + [guid]::NewGuid())
$pythonw = Join-Path $AppDir 'runtime/pythonw.exe'
$app = Start-Process -FilePath $pythonw -ArgumentList @('-I','-m','furnace_api.desktop','--workspace',('"'+$testWorkspace+'"')) -WindowStyle Hidden -PassThru
try {
  for ($attempt=0; $attempt -lt 200; $attempt++) {
    $app.Refresh()
    if ($app.HasExited) { throw 'Desktop app exited before its window opened' }
    $appHandle = [FurnaceWindow]::Find($app.Id, 'Furnace')
    if ($appHandle -ne [IntPtr]::Zero -and (Test-Path (Join-Path $testWorkspace 'studio.sqlite3'))) { break }
    Start-Sleep -Milliseconds 100
  }
  Start-Sleep -Seconds 2
  Save-Window $app (Join-Path $Screenshots 'desktop-window.png') $appHandle
  [FurnaceWindow]::PostMessage($appHandle,0x0010,[IntPtr]::Zero,[IntPtr]::Zero) | Out-Null
  if (-not $app.WaitForExit(60000)) { throw 'Closing the app did not finish cleanup' }
  if ($app.ExitCode -ne 0) { throw 'App window quit failed' }
  & (Join-Path $AppDir 'runtime/python.exe') -I -c 'import sys; from pathlib import Path; from furnace.runtime.lease import WorkspaceLease; lease=WorkspaceLease(Path(sys.argv[1])); lease.__enter__(); lease.__exit__(None,None,None)' $testWorkspace
  if ($LASTEXITCODE -ne 0) { throw 'Window quit retained the workspace lease' }
} finally {
  if (-not $app.HasExited) { Stop-Process -Id $app.Id }
}
Write-Output 'Actual installer window captured; installed app opened and closed through WM_CLOSE; lease released.'
