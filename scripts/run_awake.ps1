<#
Run a long GPU job detached and keep Windows from idle-sleeping until it ends.

  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_awake.ps1 -Bash "<bash command>"

Why: on 2026-10-12 two unattended GPU campaigns were killed when the laptop went to sleep
(System log, Kernel-Power event 42 at 19:54 UTC); Docker Desktop and every job died with it.
This holds ES_SYSTEM_REQUIRED for as long as the job runs (no admin rights needed). It does
not stop sleep caused by closing the lid, a manual sleep, or a critical battery, and it does
not keep the laptop on AC: the GPU drivers still check power and stop on battery.
#>
param([Parameter(Mandatory = $true)][string]$Bash)

Add-Type -Namespace Furnace -Name Power -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);
'@
$ES_CONTINUOUS = [uint32]"0x80000000"
$ES_SYSTEM_REQUIRED = [uint32]"0x00000001"

$bashExe = "C:\Program Files\Git\usr\bin\bash.exe"
[void][Furnace.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
try {
    $p = Start-Process $bashExe -ArgumentList '-lc', "`"$Bash`"" -WindowStyle Hidden -PassThru
    Write-Output "started bash pid $($p.Id); keeping the system awake until it exits"
    $p.WaitForExit()
    Write-Output "job exited with code $($p.ExitCode)"
}
finally {
    [void][Furnace.Power]::SetThreadExecutionState($ES_CONTINUOUS)
}
