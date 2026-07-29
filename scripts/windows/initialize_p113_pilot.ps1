[CmdletBinding()]
param(
  [string]$PlanPath = "config\p113-pilot-plan.example.json"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Capture = Join-Path $PSScriptRoot "capture_p113_hardware_snapshot.ps1"
$Runtime = Join-Path $Root ".runtime\p113"

if (-not (Test-Path -LiteralPath $Python)) {
  throw "The local Python environment is missing. Deploy the workstation runtime before initializing P113."
}

if (-not [IO.Path]::IsPathRooted($PlanPath)) {
  $PlanPath = Join-Path $Root $PlanPath
}
if (-not (Test-Path -LiteralPath $PlanPath)) {
  throw "P113 pilot plan not found: $PlanPath"
}

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$snapshot = Join-Path $Runtime "hardware-snapshot-$stamp.json"

& powershell -NoProfile -ExecutionPolicy Bypass -File $Capture -OutputPath $snapshot
if ($LASTEXITCODE -ne 0) { throw "P113 hardware snapshot failed." }

Push-Location $Root
try {
  & $Python -m src.operations.p113_pilot_initialize `
    --plan $PlanPath `
    --hardware-snapshot $snapshot
  if ($LASTEXITCODE -ne 0) { throw "P113 pilot initialization failed." }
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "P113 pilot structure is ready." -ForegroundColor Green
Write-Host "Hardware snapshot: $snapshot"
Write-Host "No model download, paid generation or public publishing was started." -ForegroundColor Yellow
