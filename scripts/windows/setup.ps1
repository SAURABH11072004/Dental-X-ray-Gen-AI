# One-time setup. From the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
# Skips anything that is already installed. Never overwrites an existing .env.
[CmdletBinding()]
param([switch]$SkipFrontend)
# "Continue" on purpose: in Windows PowerShell 5.1, "Stop" turns stderr of native tools (pip/npm/python) into
# terminating errors. Every native call below checks $LASTEXITCODE explicitly instead.
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_common.ps1"
$root = Get-ProjectRoot
Set-Location $root
Write-Step "Project root: $root"

# --- .env -----------------------------------------------------------------------------------------
if (Test-Path ".env") { Write-Ok ".env exists (left unchanged)" }
else { Copy-Item ".env.example" ".env"; Write-Ok "Created .env from .env.example" }

# --- Python + virtual environment -----------------------------------------------------------------
$venvPy = Get-VenvPython $root
if (Test-Path $venvPy) {
    Write-Ok "Virtual environment exists: .venv"
} else {
    $sys = Find-SystemPython
    if (-not $sys) { Stop-WithError "Python 3.10+ was not found on PATH." "Install Python 3.11 from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), open a new PowerShell, re-run this script." }
    Write-Step "Creating .venv with: $($sys -join ' ')"
    $exe = $sys[0]; $extra = @($sys | Select-Object -Skip 1)
    & $exe @extra -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPy)) { Stop-WithError "Could not create the virtual environment." "$($sys -join ' ') -m venv .venv" }
    Write-Ok "Created .venv"
}
Write-Ok ("venv Python: " + (& $venvPy --version))

# --- Backend dependencies ---------------------------------------------------------------------------
& $venvPy -c $DentaMindImportCheck 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "Backend dependencies already installed (requirements-api.txt)"
} else {
    Write-Step "Installing backend dependencies from requirements-api.txt"
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -r requirements-api.txt
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "pip could not install requirements-api.txt (see the pip error above; HTTP 403 = blocked by a proxy/firewall)." `
            "Check: & '$venvPy' -m pip config list ; `$env:HTTPS_PROXY ; then see docs\WINDOWS_SETUP.md section 'HTTP 403'."
    }
    & $venvPy -c $DentaMindImportCheck
    if ($LASTEXITCODE -ne 0) { Stop-WithError "Backend dependencies still do not import after installation." "& '$venvPy' -m pip install -r requirements-api.txt" }
    Write-Ok "Backend dependencies installed"
}

# --- Frontend dependencies --------------------------------------------------------------------------
if (-not $SkipFrontend) {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Stop-WithError "Node.js was not found on PATH." "Install Node.js 20 LTS from https://nodejs.org, open a new PowerShell, re-run this script." }
    $nodeV = (& node --version).TrimStart("v")
    if ([int]($nodeV.Split(".")[0]) -lt 18) { Stop-WithError "Node.js $nodeV is too old; Vite 5 needs 18+." "Install Node.js 20 LTS from https://nodejs.org" }
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { Stop-WithError "npm was not found." "Reinstall Node.js (npm is included)." }
    Write-Ok "Node.js $nodeV, npm $(& npm.cmd --version)"
    Push-Location (Join-Path $root "frontend")
    try {
        $haveVite = Test-Path "node_modules\.bin\vite.cmd"
        if ($haveVite) { & npm.cmd ls --depth=0 *> $null }
        if ($haveVite -and $LASTEXITCODE -eq 0) {
            Write-Ok "Frontend dependencies already installed (frontend\node_modules)"
        } else {
            Write-Step "Installing frontend dependencies from frontend\package.json"
            & npm.cmd install
            if ($LASTEXITCODE -ne 0) {
                Stop-WithError "npm install failed (see the npm error above; E403 = blocked by a proxy/firewall/registry policy)." `
                    "Check: npm.cmd config get registry ; npm.cmd config get https-proxy ; then see docs\WINDOWS_SETUP.md section 'HTTP 403'."
            }
            if (-not (Test-Path "node_modules\.bin\vite.cmd")) { Stop-WithError "npm install finished but Vite is missing." "cd frontend; npm.cmd install" }
            Write-Ok "Frontend dependencies installed"
        }
    } finally { Pop-Location }
}

# --- Environment report ------------------------------------------------------------------------------
Write-Step "Environment report"
& $venvPy scripts\validate_environment.py
Write-Host ""
Write-Ok "Setup finished. Next: powershell -ExecutionPolicy Bypass -File scripts\windows\start_all.ps1"
