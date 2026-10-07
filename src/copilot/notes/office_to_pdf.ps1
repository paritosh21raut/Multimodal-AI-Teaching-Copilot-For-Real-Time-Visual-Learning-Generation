# A Word / PowerPoint file -> PDF through the installed Microsoft Office (F-010b: the teacher's notes).
# Hidden, read-only, no dialogs. Usage: powershell -File office_to_pdf.ps1 -App word|powerpoint -In <file> -Out <pdf>
param([Parameter(Mandatory = $true)][string]$App, [Parameter(Mandatory = $true)][string]$In,
      [Parameter(Mandatory = $true)][string]$Out)
$ErrorActionPreference = "Stop"
if ($App -eq "word") {
  $word = New-Object -ComObject Word.Application
  try {
    $word.Visible = $false
    $word.DisplayAlerts = 0
    # FileName, ConfirmConversions, ReadOnly, AddToRecentFiles
    $doc = $word.Documents.Open($In, $false, $true, $false)
    try { $doc.ExportAsFixedFormat($Out, 17) } finally { $doc.Close(0) }  # 17 = PDF; close without saving
  } finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
  }
} else {
  $ppt = New-Object -ComObject PowerPoint.Application
  try {
    $pres = $ppt.Presentations.Open($In, $true, $false, $false)  # read-only, no title, no window
    try { $pres.SaveAs($Out, 32) } finally { $pres.Close() }       # 32 = PDF
  } finally {
    $ppt.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
  }
}
Write-Output "ok"
