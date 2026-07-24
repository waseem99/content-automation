[CmdletBinding()]
param(
  [string]$TaskName = "ContentAutomationLocal",
  [switch]$ExposeWithNgrok
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$Supervisor = Join-Path $PSScriptRoot "supervise_always_on_local_production.ps1"
if (-not (Test-Path (Join-Path $Root ".env.local"))) {
  throw "Run deploy_always_on_local_production.ps1 to create the local environment first."
}
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

$arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Supervisor`""
if ($ExposeWithNgrok) { $arguments += " -ExposeWithNgrok" }
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -WakeToRun -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started scheduled task '$TaskName'." -ForegroundColor Green
Write-Host "The runtime starts automatically at Windows sign-in and the task/supervisor restart failures."
