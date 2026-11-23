$ErrorActionPreference = 'Stop'
# Inno Setup 6.4.3 permits free commercial use. Pin the official GitHub asset digest.
$toolsDir = Join-Path $PSScriptRoot '../dist/build-tools'
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$installerPath = Join-Path $toolsDir 'innosetup-6.4.3.exe'
Invoke-WebRequest 'https://github.com/jrsoftware/issrc/releases/download/is-6_4_3/innosetup-6.4.3.exe' -OutFile $installerPath
$expectedHash = 'f3c42116542c4cc57263c5ba6c4feabfc49fe771f2f98a79d2f7628b8762723b'
if ((Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLower() -ne $expectedHash) { throw 'Compiler checksum mismatch' }
$compilerDir = [IO.Path]::GetFullPath((Join-Path $toolsDir 'inno'))
$process = Start-Process -FilePath $installerPath -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER',('/DIR="' + $compilerDir + '"')) -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Compiler installation failed: $($process.ExitCode)" }
Write-Output (Join-Path $compilerDir 'ISCC.exe')
