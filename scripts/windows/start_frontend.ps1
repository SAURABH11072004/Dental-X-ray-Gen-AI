# Starts the real Vite dev server on http://localhost:<Port>; /api is proxied to -ApiTarget. Ctrl+C stops it.
[CmdletBinding()]
param([int]$Port = 5173, [string]$ApiTarget = "")
# "Continue" on purpose: in Windows PowerShell 5.1, "Stop" turns stderr of native tools (pip/npm/python) into
# terminating errors. Every native call below checks $LASTEXITCODE explicitly instead.
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_common.ps1"
$root = Get-ProjectRoot
Set-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules\.bin\vite.cmd")) { Stop-WithError "Frontend dependencies are missing (frontend\node_modules)." "powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1" }
Assert-PortFree $Port "the frontend"
if ($ApiTarget) { $env:VITE_API_TARGET = $ApiTarget }
$target = if ($env:VITE_API_TARGET) { $env:VITE_API_TARGET } else { "http://127.0.0.1:8000 (default; override in frontend\.env)" }
Write-Step "Starting Vite on http://localhost:$Port ; /api -> $target"
& npm.cmd run dev -- --port $Port --strictPort
exit $LASTEXITCODE
