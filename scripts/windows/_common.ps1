# Shared helpers for the DentaMind Windows scripts. Dot-source it:  . "$PSScriptRoot\_common.ps1"
# Compatible with Windows PowerShell 5.1 and PowerShell 7+. No machine-specific paths.

function Get-ProjectRoot { (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Warn2([string]$msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail([string]$msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

function Stop-WithError([string]$msg, [string]$next) {
    Write-Fail $msg
    if ($next) { Write-Host "       Next step: $next" -ForegroundColor Yellow }
    exit 1
}

# Returns the command (array) that runs a system Python >= 3.10, or $null.
function Find-SystemPython {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidates += ,@("py", "-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += ,@("python") }
    foreach ($c in $candidates) {
        $exe = $c[0]; $extra = @($c | Select-Object -Skip 1)
        $v = & $exe @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -match '^(\d+)\.(\d+)$') {
            if ([int]$Matches[1] -gt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 10)) { return ,$c }
            Write-Warn2 "$exe reports Python $v; 3.10 or newer is required."
        }
    }
    return $null
}

function Get-VenvPython([string]$root) { Join-Path $root ".venv\Scripts\python.exe" }

# Python one-liner that exits 0 only if every backend dependency imports.
$Global:DentaMindImportCheck = "import fastapi, uvicorn, pydantic, numpy, PIL, yaml, dotenv, importlib.util as u; assert u.find_spec('python_multipart') or u.find_spec('multipart'), 'python-multipart missing'"

# True if nothing is listening on the port (IPv4 and IPv6 loopback).
function Test-PortFree([int]$Port) {
    foreach ($addr in @([System.Net.IPAddress]::Loopback, [System.Net.IPAddress]::IPv6Loopback)) {
        $l = $null
        try { $l = New-Object System.Net.Sockets.TcpListener($addr, $Port); $l.Start() }
        catch {
            $e = $_.Exception
            while ($e.InnerException) { $e = $e.InnerException }
            # AddressAlreadyInUse (10048) or AccessDenied (10013, e.g. a Hyper-V reserved port) = not usable.
            # Other errors (e.g. IPv6 disabled on this machine) are not a conflict.
            if ($e -is [System.Net.Sockets.SocketException] -and ($e.ErrorCode -eq 10048 -or $e.ErrorCode -eq 10013)) { return $false }
        }
        finally { if ($l) { try { $l.Stop() } catch { } } }
    }
    return $true
}

function Get-PortOwner([int]$Port) {
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        return "PID $($c.OwningProcess) ($($p.ProcessName))"
    } catch { return "unknown process" }
}

function Assert-PortFree([int]$Port, [string]$what) {
    if (-not (Test-PortFree $Port)) {
        Stop-WithError "Port $Port (needed for $what) is already in use by $(Get-PortOwner $Port)." `
            "Stop that process (taskkill /PID <pid> /F) or start with a different port, e.g. -Port $($Port + 1)."
    }
}

# GET a URL; returns @{ ok; status; body; error } and never throws.
# Authorization header for the local API (token from DENTAMIND_API_TOKEN or runtime\api_token.txt); empty when there is none.
function Get-ApiHeaders {
    $t = $env:DENTAMIND_API_TOKEN
    if (-not $t) { $f = Join-Path (Get-ProjectRoot) "runtime\api_token.txt"; if (Test-Path $f) { $t = (Get-Content $f -Raw).Trim() } }
    if ($t) { return @{ Authorization = "Bearer $t" } } else { return @{} }
}

function Invoke-Probe([string]$url, [string]$method = "GET", [int]$timeout = 10) {
    try {
        $r = Invoke-WebRequest -Uri $url -Method $method -UseBasicParsing -TimeoutSec $timeout -Headers (Get-ApiHeaders)
        return @{ ok = $true; status = [int]$r.StatusCode; body = $r.Content; error = $null }
    } catch {
        $status = $null; $body = $null
        if ($_.Exception.Response) { try { $status = [int]$_.Exception.Response.StatusCode } catch { } }
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $body = $_.ErrorDetails.Message }
        return @{ ok = $false; status = $status; body = $body; error = $_.Exception.Message }
    }
}
