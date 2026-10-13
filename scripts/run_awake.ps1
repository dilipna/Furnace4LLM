<#
Run a long GPU job detached and keep Windows from idle-sleeping until it ends.

  powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\furnace\scripts\run_awake.ps1 -Script bench/run_remaining_gpu.sh
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\furnace\scripts\run_awake.ps1 -Bash '<bash command>'

-Script runs a script from the repository root with uv on PATH (the normal use). -Bash takes an
inline command; when it is passed through `powershell -File`, Windows PowerShell 5.1 does not
escape double quotes inside it and splits the argument, so an inline command must not contain
double quotes (use -Script instead).

What it does: holds ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED for as long as the job runs (no
admin rights needed), so neither the idle-sleep timer nor a display timeout can put the machine
into sleep or Modern Standby (this laptop uses S0 Low Power Idle; on 2026-10-11 it entered
standby on a "Screen Off Request"). It stops with an error if Windows refuses the request. The
bash command is written to a temporary script file and run with `bash -l <file>`, so quotes
inside it need no escaping. The exit code is the job's.

What it cannot prevent (checked 2026-10-13 in the System log): the sleeps that killed the
2026-10-12 runs (Kernel-Power 42 at 05:22 and 19:54 UTC) were requested through winlogon.exe
(Kernel-Power 187: SetSuspendState), which is Windows' own Sleep command (Start > Power >
Sleep or equivalent), not an idle timeout. No execution-state request blocks that, nor a
critical-battery sleep. Do not choose Sleep while a job runs; keep the laptop on AC (the GPU
drivers stop on battery). A killed job resumes without rerunning finished units.
#>
param([string]$Script, [string]$Bash)
if ([string]::IsNullOrEmpty($Script) -eq [string]::IsNullOrEmpty($Bash)) {
    Write-Error "pass exactly one of -Script <path relative to the repo> or -Bash '<command>'"
    exit 2
}
if ($Script) {
    $repo = Split-Path -Parent $PSScriptRoot
    if (-not (Test-Path (Join-Path $repo $Script))) { Write-Error "no such script: $Script"; exit 2 }
    $root = "/" + $repo.Substring(0, 1).ToLower() + $repo.Substring(2).Replace("\", "/")  # C:\dev\furnace -> /c/dev/furnace
    $Bash = "export PATH=/c/Users/user/.local/bin:`$PATH; cd '$root' && bash '$Script'"
}

Add-Type -Namespace Furnace -Name Power -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);
'@
$ES_CONTINUOUS = [uint32]"0x80000000"
$ES_SYSTEM_REQUIRED = [uint32]"0x00000001"
$ES_DISPLAY_REQUIRED = [uint32]"0x00000002"

$bashExe = "C:\Program Files\Git\usr\bin\bash.exe"
$script = Join-Path ([IO.Path]::GetTempPath()) ("furnace-job-" + [Guid]::NewGuid().ToString("N") + ".sh")
[IO.File]::WriteAllText($script, $Bash + "`n", (New-Object Text.UTF8Encoding($false)))
$prev = [Furnace.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_DISPLAY_REQUIRED)
if ($prev -eq 0) {
    Remove-Item $script -ErrorAction SilentlyContinue
    Write-Error "SetThreadExecutionState refused the keep-awake request; not starting the job"
    exit 2
}
$code = 1
try {
    $p = Start-Process $bashExe -ArgumentList '-l', ('"' + $script + '"') -WindowStyle Hidden -PassThru
    Write-Output "$((Get-Date).ToUniversalTime().ToString('s'))Z started bash pid $($p.Id); keeping the system and display awake until it exits"
    $p.WaitForExit()
    $code = $p.ExitCode
    Write-Output "$((Get-Date).ToUniversalTime().ToString('s'))Z job exited with code $code"
}
finally {
    [void][Furnace.Power]::SetThreadExecutionState($ES_CONTINUOUS)
    Remove-Item $script -ErrorAction SilentlyContinue
}
exit $code
