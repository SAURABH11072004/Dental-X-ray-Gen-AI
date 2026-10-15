# Re-runs the functionality audit against the RUNNING servers (API :8000, UI :5173) and records every command, exit code and duration.
#   powershell -NoProfile -File scripts\run_audit_suite.ps1
# Output: docs\audit_evidence\suite_log.json plus one .log per step. Needs: servers running, .venv, nothing else using the GPU.
# It creates a few audit records (uploads, analyses, reports) in the app database; it never deletes or overwrites checkpoints,
# datasets or existing reports. The browser audit (Node + playwright-core + Edge) is separate: see docs/FUNCTIONALITY_AUDIT.md.
[CmdletBinding()]
param([switch]$SkipUnitTests)
$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
$ev = Join-Path $root "docs\audit_evidence"
New-Item -ItemType Directory -Force $ev | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$steps = @()
if (-not $SkipUnitTests) { $steps += ,@("unit_tests", $py, @("-m", "unittest", "discover", "-s", "tests", "-v")) }
$steps += ,@("live_api", $py, @("scripts\audit_live_api.py"))
$steps += ,@("models", $py, @("scripts\audit_models.py"))
$steps += ,@("reports", $py, @("scripts\audit_reports.py"))
$steps += ,@("no_numbering", $py, @("scripts\audit_no_numbering.py"))
$steps += ,@("approved_training_dry_run", $py, @("scripts\audit_approved_training.py"))
$steps += ,@("training_api", $py, @("scripts\audit_training_api.py"))
$steps += ,@("windows_check_running", "powershell", @("-NoProfile", "-File", "scripts\windows\check_running.ps1"))
$steps += ,@("security_live", $py, @("scripts\audit_security_live.py"))      # last: it fills the rate-limit buckets and waits for the windows to slide (about 4 minutes)
$log = @()
foreach ($s in $steps) {
    $name, $exe, $args_ = $s[0], $s[1], $s[2]
    $out = Join-Path $ev "$name.log"
    $t = [Diagnostics.Stopwatch]::StartNew()
    # cmd.exe redirection keeps the child's UTF-8 bytes (Windows PowerShell 5.1's *> would write UTF-16)
    $quoted = (@($exe) + @($args_) | ForEach-Object { if ("$_" -match '\s') { '"' + $_ + '"' } else { "$_" } }) -join ' '
    & cmd.exe /d /c "$quoted > `"$out`" 2>&1"
    $code = $LASTEXITCODE
    $t.Stop()
    $tail = (Get-Content $out -Tail 4 -ErrorAction SilentlyContinue) -join " | "
    $log += [ordered]@{ step = $name; command = "$exe $($args_ -join ' ')"; exit_code = $code; seconds = [math]::Round($t.Elapsed.TotalSeconds, 1); log = "docs/audit_evidence/$name.log"; tail = $tail }
    Write-Host ("{0,-24} exit={1} {2,6:N1}s  {3}" -f $name, $code, $t.Elapsed.TotalSeconds, $tail.Substring(0, [Math]::Min(120, $tail.Length)))
}
@{ run_at = (Get-Date -Format s); host = $env:COMPUTERNAME; steps = $log } | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $ev "suite_log.json") -Encoding utf8
$bad = @($log | Where-Object { $_.exit_code -ne 0 }).Count
if ($bad -gt 0) { Write-Host "$bad step(s) exited non-zero (see logs)"; exit 1 } else { Write-Host "All steps exited 0 (this is the exit code, not the per-test verdicts: read each log's SUMMARY line)"; exit 0 }
