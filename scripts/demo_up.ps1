# Start the whole demo stack and run the pre-flight check.
#
#   powershell -ExecutionPolicy Bypass -File scripts/demo_up.ps1            # start (restarts app processes)
#   powershell -ExecutionPolicy Bypass -File scripts/demo_up.ps1 -Stop      # stop app processes + vLLM
#   (or: uv run poe demo-up / uv run poe demo-down)
#
# Docker Desktop, Postgres (:5433) and the lab vLLM (:8100) are started if needed; the API
# (:8010, no --reload), scan worker, Guard runner and web (:3100) are (re)started hidden, with
# logs in .data/logs/. The web app runs as a production build; -Dev runs `next dev` instead.
# Ends with scripts/preflight.py --load.
param([switch]$Stop, [switch]$Dev, [string]$Owner = "")

$ErrorActionPreference = "Continue"  # docker writes progress to stderr
$Root = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $Root ".data\logs"
New-Item -ItemType Directory -Force $Logs | Out-Null
$Bash = "C:\Program Files\Git\usr\bin\bash.exe"
$HfHome = "C:/Users/$env:USERNAME/.cache/huggingface"

function Stop-App {
    # app processes by command line, then anything still listening on the app ports (and its
    # children: uvicorn/multiprocessing workers on Windows keep the socket otherwise)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match 'furnace' -and
        $_.CommandLine -match 'furnace_api.main:app|furnace.jobs.worker|poe (api|worker|runner)|next (dev|start)|next-server|pnpm (dev|start)'
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    foreach ($port in 8010, 3100) {
        $owners = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).OwningProcess
        foreach ($o in $owners) {
            Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $o -or $_.ProcessId -eq $o } |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        }
    }
}

function Start-Hidden([string]$Name, [string]$Command) {
    $log = "$($Logs -replace '\\','/')/$Name.log"
    $cmd = "export PATH=/c/Users/$env:USERNAME/.local/bin:`$PATH; export PYTHONIOENCODING=utf-8; cd '$($Root -replace '\\','/')' && $Command > '$log' 2>&1"
    Start-Process -FilePath $Bash -ArgumentList '-lc', "`"$cmd`"" -WindowStyle Hidden | Out-Null
    Write-Host "started $Name (log: .data/logs/$Name.log)"
}

function Wait-Url([string]$Name, [string]$Url, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            if ((Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200) {
                Write-Host "ready   $Name"; return $true
            }
        } catch { Start-Sleep -Seconds 2 }
    }
    Write-Host "TIMEOUT $Name ($Url)"; return $false
}

Set-Location $Root
if ($Stop) {
    Stop-App
    docker stop furnace-vllm-1 2>$null | Out-Null
    Write-Host "stopped app processes and vLLM (Postgres and Docker left running)"
    exit 0
}

# Docker Desktop
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Start-Process "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
    Write-Host "starting Docker Desktop..."
    $deadline = (Get-Date).AddSeconds(180)
    do { Start-Sleep -Seconds 3; docker info *> $null } until ($LASTEXITCODE -eq 0 -or (Get-Date) -gt $deadline)
}
docker compose up -d postgres | Out-Null
$env:HF_HOME_HOST = $HfHome
docker compose --profile gpu up -d vllm | Out-Null

Stop-App
Start-Sleep -Seconds 1
Start-Hidden "api" "uv run uvicorn furnace_api.main:app --port 8010 --timeout-graceful-shutdown 3"
Start-Hidden "worker" "uv run python -m furnace.jobs.worker --queues cpu"
Start-Hidden "runner" "uv run python -m furnace.jobs.worker --queues runner"
if ($Dev) {
    Start-Hidden "web" "cd apps/web && pnpm dev --port 3100"
} else {
    # production build: fast first page loads on stage and no dev overlay
    Start-Hidden "web" "cd apps/web && pnpm build && pnpm start --port 3100"
}

$ok = (Wait-Url "api" "http://localhost:8010/healthz" 90) -and
      (Wait-Url "lab vLLM" "http://localhost:8100/v1/models" 240) -and
      (Wait-Url "web" "http://localhost:3100/" 300)
if (-not $ok) { Write-Host "see .data/logs/*.log"; exit 1 }

Start-Sleep -Seconds 5  # worker/runner register within a few seconds
$pf = @("run", "python", "scripts/preflight.py", "--load")
if ($Owner) { $pf += @("--owner", $Owner) }
& uv @pf
exit $LASTEXITCODE
