[CmdletBinding()]
param(
  [string]$TaskName = "ContentAutomation-ProviderWorkers"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$Supervisor = Join-Path $PSScriptRoot "supervise_provider_workers.ps1"
$StopMarker = Join-Path $Runtime "provider-workers.stop"

if (-not (Test-Path -LiteralPath (Join-Path $Root ".env.local"))) {
  throw "The local Content Automation environment is not installed."
}
if (-not (Test-Path -LiteralPath $Supervisor)) {
  throw "Provider worker supervisor is missing."
}

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
New-Item -ItemType File -Force -Path $StopMarker | Out-Null
Start-Sleep -Seconds 2
Remove-Item $StopMarker -Force -ErrorAction SilentlyContinue

$arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Supervisor`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -WakeToRun -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started scheduled task '$TaskName'." -ForegroundColor Green
Write-Host "Paid requests still require an approved P94 route and spend reservation." -ForegroundColor Yellow
