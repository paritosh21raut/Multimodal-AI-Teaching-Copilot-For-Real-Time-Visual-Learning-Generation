# Export every slide of a .pptx to PNG through the installed PowerPoint (F-010 check: the PPTX must look like the
# projector). Usage: powershell -File tools/pptx_to_png.ps1 <file.pptx> <out dir>
param([Parameter(Mandatory = $true)][string]$Pptx, [Parameter(Mandatory = $true)][string]$Out)
$ErrorActionPreference = "Stop"
$pptxPath = (Resolve-Path $Pptx).Path
New-Item -ItemType Directory -Force $Out | Out-Null
$outPath = (Resolve-Path $Out).Path
$app = New-Object -ComObject PowerPoint.Application
try {
  $pres = $app.Presentations.Open($pptxPath, $true, $false, $false)  # read-only, no title, no window
  try {
    foreach ($slide in $pres.Slides) {
      $file = Join-Path $outPath ("ppt{0:D2}.png" -f $slide.SlideIndex)
      $slide.Export($file, "PNG", 1920, 1080)
    }
    Write-Output "$($pres.Slides.Count) slides -> $outPath"
  } finally { $pres.Close() }
} finally {
  $app.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
