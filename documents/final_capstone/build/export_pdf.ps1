# Export a .docx to PDF next to it with Word.  powershell -NoProfile -File export_pdf.ps1 <path.docx>
param([string]$docx)
$ErrorActionPreference = "Stop"
$pdf = [IO.Path]::ChangeExtension($docx, ".pdf")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($docx, $false, $false, $false)
    $doc.ExportAsFixedFormat([string]$pdf, 17)
    Write-Output ("pages: {0}" -f $doc.ComputeStatistics(2))
    $doc.Close($false)
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
