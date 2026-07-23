[CmdletBinding()]
param(
  [string]$TaskName = "ContentAutomationLocal",
  [switch]$KeepTask
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
Set-Content -LiteralPath (Join-Path $Runtime "stop.request") -Value (Get-Date).ToUniversalTime().ToString("o") -Encoding ascii
$deadline = (Get-Date).AddSeconds(30)
do {
  Start-Sleep -Seconds 1
  $pidFile = Join-Path $Runtime "supervisor.pid"
  $running = $false
  if (Test-Path $pidFile) {
    $value = [int](Get-Content $pidFile -Raw)
    $running = [bool](Get-Process -Id $value -ErrorAction SilentlyContinue)
  }
} until (-not $running -or (Get-Date) -gt $deadline)
if ($running) { Stop-Process -Id $value -Force -ErrorAction SilentlyContinue }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if (-not $KeepTask) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
}
Write-Host "Always-on local production stopped. Database, models, queue, and artifacts were preserved."
