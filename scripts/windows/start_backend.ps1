# Starts the real FastAPI backend (uvicorn) on http://127.0.0.1:<Port>. Runs in the foreground; Ctrl+C stops it.
[CmdletBinding()]
param([int]$Port = 8000, [switch]$NoReload)
# "Continue" on purpose: in Windows PowerShell 5.1, "Stop" turns stderr of native tools (pip/npm/python) into
# terminating errors. Every native call below checks $LASTEXITCODE explicitly instead.
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_common.ps1"
$root = Get-ProjectRoot
Set-Location $root
$venvPy = Get-VenvPython $root
if (-not (Test-Path $venvPy)) { Stop-WithError ".venv not found." "powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1" }
& $venvPy -c $DentaMindImportCheck
if ($LASTEXITCODE -ne 0) { Stop-WithError "Backend dependencies are missing in .venv." "powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1" }
Assert-PortFree $Port "the backend"
Write-Step "Starting backend: uvicorn backend.main:app on http://127.0.0.1:$Port  (API docs: /docs)"
$uvArgs = @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$Port")
if (-not $NoReload) { $uvArgs += @("--reload", "--reload-dir", "backend", "--reload-dir", "src") }
& $venvPy @uvArgs
exit $LASTEXITCODE
