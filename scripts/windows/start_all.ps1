# Opens the backend and the frontend in two new PowerShell windows, waits until both answer,
# then runs check_running.ps1. Reports success only if the checks pass.
[CmdletBinding()]
param([int]$ApiPort = 8000, [int]$WebPort = 5173, [int]$TimeoutSec = 90)
# "Continue" on purpose: in Windows PowerShell 5.1, "Stop" turns stderr of native tools (pip/npm/python) into
# terminating errors. Every native call below checks $LASTEXITCODE explicitly instead.
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_common.ps1"
$root = Get-ProjectRoot
Assert-PortFree $ApiPort "the backend"
Assert-PortFree $WebPort "the frontend"
$ps = (Get-Process -Id $PID).Path
$api = "http://127.0.0.1:$ApiPort"
Start-Process -FilePath $ps -WorkingDirectory $root -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$PSScriptRoot\start_backend.ps1`"", "-Port", "$ApiPort")
Write-Step "Backend window opened; waiting for $api/api/health ..."
$deadline = (Get-Date).AddSeconds($TimeoutSec)
do { Start-Sleep -Seconds 2; $h = Invoke-Probe "$api/api/health?probes=false" "GET" 5 } until ($h.ok -or (Get-Date) -gt $deadline)
if (-not $h.ok) { Stop-WithError "Backend did not become healthy within $TimeoutSec s ($($h.error))." "Read the error in the backend window." }
Write-Ok "Backend is answering"
Start-Process -FilePath $ps -WorkingDirectory $root -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$PSScriptRoot\start_frontend.ps1`"", "-Port", "$WebPort", "-ApiTarget", $api)
Write-Step "Frontend window opened; waiting for http://localhost:$WebPort ..."
$deadline = (Get-Date).AddSeconds($TimeoutSec)
do { Start-Sleep -Seconds 2; $f = Invoke-Probe "http://localhost:$WebPort/" "GET" 5 } until ($f.ok -or (Get-Date) -gt $deadline)
if (-not $f.ok) { Stop-WithError "Frontend did not answer within $TimeoutSec s ($($f.error))." "Read the error in the frontend window." }
& "$PSScriptRoot\check_running.ps1" -ApiPort $ApiPort -WebPort $WebPort
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Start-Process "http://localhost:$WebPort/"
