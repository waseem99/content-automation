[CmdletBinding()]
param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$RemoteUrl = "",
  [switch]$Headed,
  [switch]$OpenReport
)

$runner = Join-Path $PSScriptRoot "run_platform_acceptance.ps1"
& $runner -BaseUrl $BaseUrl -RemoteUrl $RemoteUrl -Headed:$Headed -Smoke -OpenReport:$OpenReport -SkipBackup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
