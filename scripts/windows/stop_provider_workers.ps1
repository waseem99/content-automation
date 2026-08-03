[CmdletBinding()]
param(
  [string]$TaskName = "ContentAutomation-ProviderWorkers",
  [switch]$RemoveTask
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$StopMarker = Join-Path $Runtime "provider-workers.stop"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
New-Item -ItemType File -Force -Path $StopMarker | Out-Null
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
if ($RemoveTask) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
}
Write-Host "Provider workers stopped. Queued jobs and spend evidence remain in PostgreSQL." -ForegroundColor Green
