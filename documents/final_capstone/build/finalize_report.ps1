# Opens the generated report in Word, updates the table of contents, the lists of figures/tables and all fields,
# saves the .docx and exports the PDF (with heading bookmarks).
# Run:  powershell -NoProfile -File documents\final_capstone\build\finalize_report.ps1
$ErrorActionPreference = "Stop"
$Base = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$docx = Join-Path $Base "DentaMind_AI_Capstone_Report.docx"
$pdf  = Join-Path $Base "DentaMind_AI_Capstone_Report.pdf"
$sw = [Diagnostics.Stopwatch]::StartNew()
function Log($m) { Write-Output ("[{0,5:N1}s] {1}" -f $sw.Elapsed.TotalSeconds, $m) }
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($docx, $false, $false, $false)
    Log "opened"
    $n = $doc.TablesOfContents.Count
    Log "TOC fields: $n"
    for ($pass = 1; $pass -le 2; $pass++) {
        for ($i = 1; $i -le $n; $i++) { $doc.TablesOfContents.Item($i).Update(); Log "pass $pass updated TOC $i" }
    }
    # the lists of figures / tables are TOC fields built from caption styles: give them the 'table of figures' look
    for ($i = 2; $i -le $n; $i++) { $doc.TablesOfContents.Item($i).Range.Style = "table of figures" }
    for ($i = 1; $i -le $n; $i++) { $doc.TablesOfContents.Item($i).UpdatePageNumbers() }
    Log "page numbers updated"
    $doc.Save()
    Log "saved docx"
    $doc.ExportAsFixedFormat([string]$pdf, 17)
    Log "exported pdf"
    $pages = $doc.ComputeStatistics(2)
    Log "pages: $pages"
    $doc.Close($false)
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
