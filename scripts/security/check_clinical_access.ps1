# Read-only access test for the clinical-review files (PROPOSED procedure, reports/security/clinical_files_access_control_plan_PROPOSED.md).
# Run it while logged in as the account under test, e.g. a non-privileged reviewer account. It opens each path for reading and closes
# it immediately. It prints only the path and DENIED / READABLE / MISSING, never any file content. It changes nothing.
#
#   powershell -ExecutionPolicy Bypass -File scripts\security\check_clinical_access.ps1 [-RepoRoot "D:\Dentex-Gen Ai"] [-ShareRoot "<reviewer share>"]
param(
    [string]$RepoRoot = "D:\Dentex-Gen Ai",
    [string]$ShareRoot = ""
)

$mustBeDenied = @(
    "reports\clinical_review\caries_rereading_key_v1_COORDINATOR_ONLY.csv",
    "reports\clinical_review\caries_rereading_key_v2_COORDINATOR_ONLY.csv",
    "reports\clinical_review\caries_rereading_worksheet_v1_BLINDED.csv",
    "reports\cv5_caries_clinician_review_list.csv",
    "kaggle\artifacts_cv5_run1\caries_confusion_findings.csv",
    "kaggle\dentamind_5fold_cv_artifacts.zip",
    "scripts\build_clinician_review_queue.py"
)

function Test-Read([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return "MISSING" }
    try {
        $fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $fs.Close()
        return "READABLE"
    } catch [System.UnauthorizedAccessException] {
        return "DENIED"
    } catch {
        return "ERROR: " + $_.Exception.GetType().Name
    }
}

$who = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
"account: $who ; elevated administrator: $admin ; date: " + (Get-Date -Format o)
$fail = $false
foreach ($rel in $mustBeDenied) {
    $r = Test-Read (Join-Path $RepoRoot $rel)
    "{0,-10} {1}" -f $r, $rel
    if ($r -eq "READABLE") { $fail = $true }
}
if ($ShareRoot -ne "") {
    $ws = Join-Path $ShareRoot "caries_rereading_worksheet_v2_BLINDED.csv"
    $r = Test-Read $ws
    "{0,-10} {1}  (reviewer worksheet: must be READABLE for an authorized reviewer)" -f $r, $ws
    if ($r -ne "READABLE") { $fail = $true }
}
if ($fail) { "RESULT: FAIL - access is NOT restricted as required for this account" } else { "RESULT: PASS for this account" }
