# Verifies RUNNING servers with real HTTP requests. Changes nothing. Exit code 0 only if every required check passes.
[CmdletBinding()]
param([int]$ApiPort = 8000, [int]$WebPort = 5173, [switch]$BackendOnly)
. "$PSScriptRoot\_common.ps1"
$api = "http://127.0.0.1:$ApiPort"; $web = "http://localhost:$WebPort"
$failed = 0
function Check([string]$name, [bool]$ok, [string]$detail) { if ($ok) { Write-Ok "$name - $detail" } else { Write-Fail "$name - $detail"; $script:failed++ } }

$h = Invoke-Probe "$api/api/health?probes=false"
Check "Backend health ($api/api/health)" $h.ok $(if ($h.ok) { $j = $h.body | ConvertFrom-Json; "backend=$($j.backend) version=$($j.version) database=$($j.database) checkpoints=$($j.checkpoints_loaded)" } else { $h.error })
if (-not $h.ok) { Write-Host "Backend is not running. Start it: powershell -ExecutionPolicy Bypass -File scripts\windows\start_backend.ps1"; exit 1 }

$d = Invoke-Probe "$api/api/dataset/status"
if ($d.ok) { $j = $d.body | ConvertFrom-Json; Check "Dataset status" $true "state=$($j.state) test_images=$($j.test_image_count) main_images=$($j.main_image_count)" } else { Check "Dataset status" $false $d.error }

$i = Invoke-Probe "$api/api/images?source=all&limit=1"
if ($i.ok) {
    $j = $i.body | ConvertFrom-Json
    Check "Image list" ($j.total -gt 0) "total=$($j.total)"
    if ($j.total -gt 0) {
        $first = $j.items[0]
        $f = Invoke-Probe ("$api" + $first.url)
        Check "Image file download" ($f.ok) "$($first.filename) $($first.width)x$($first.height) HTTP $($f.status)"
        $pr = $null
        try { $pr = Invoke-RestMethod -Uri "$api/api/predict" -Method Post -ContentType "application/json" -Headers (Get-ApiHeaders) -Body (@{ image_id = $first.id } | ConvertTo-Json) -TimeoutSec 30 } catch { $pr = $_ }
        if ($pr -is [System.Management.Automation.ErrorRecord]) {
            $msg = if ($pr.ErrorDetails) { ($pr.ErrorDetails.Message | ConvertFrom-Json).error } else { $null }
            Check "Detection without a trained model" ($null -ne $msg) "returns error '$($msg.code)': $($msg.message) (this is only expected when no dental checkpoint is registered)"
        } else {
            Check "Real detection on the first image" ($pr.detections.Count -ge 0 -and [bool]$pr.model_version) "model $($pr.model_version) returned $($pr.detections.Count) detections"
        }
    }
} else { Check "Image list" $false $i.error }

if (-not $BackendOnly) {
    $w = Invoke-Probe "$web/"
    Check "Frontend page ($web)" ($w.ok -and $w.body -match 'id="root"') $(if ($w.ok) { "HTTP $($w.status)" } else { $w.error })
    $x = Invoke-Probe "$web/api/health?probes=false"
    Check "Frontend proxy -> backend ($web/api/health)" $x.ok $(if ($x.ok) { "proxied OK" } else { "$($x.error) - check VITE_API_TARGET in frontend\.env" })
}
Write-Host ""
if ($failed -eq 0) { Write-Ok "All checks passed. Open $web" ; exit 0 } else { Write-Fail "$failed check(s) failed."; exit 1 }
