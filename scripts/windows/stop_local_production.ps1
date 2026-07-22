[CmdletBinding()]
param([switch]$KeepDatabase)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
foreach ($name in "ngrok", "worker", "api") {
  $file = Join-Path $Runtime "$name.pid"
  if (-not (Test-Path $file)) { continue }
  $pidValue = [int](Get-Content $file -Raw)
  $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
  if ($process) { Stop-Process -Id $pidValue -Force }
  Remove-Item $file -Force
}
if (-not $KeepDatabase) {
  Push-Location $Root
  try { docker compose --env-file .env.local -f compose.local.yml down }
  finally { Pop-Location }
}
Write-Host "Local content production runtime stopped. Models, database volume, and artifacts were preserved."
