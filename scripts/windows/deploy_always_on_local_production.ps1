[CmdletBinding()]
param(
  [switch]$EnableComfyUI,
  [switch]$AcceptComfyModelLicense,
  [switch]$ExposeWithNgrok,
  [switch]$SkipInstall,
  [switch]$SkipModelPull
)

$ErrorActionPreference = "Stop"
$Start = Join-Path $PSScriptRoot "start_local_production.ps1"
$StopManual = Join-Path $PSScriptRoot "stop_local_production.ps1"
$StopAlwaysOn = Join-Path $PSScriptRoot "stop_always_on_local_production.ps1"
$InstallTask = Join-Path $PSScriptRoot "install_local_production_service.ps1"

# Make repeated deployment idempotent. Existing database, models, artifacts, and
# queued jobs are preserved.
& $StopAlwaysOn -KeepTask

$arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Start)
if ($EnableComfyUI) { $arguments += "-EnableComfyUI" }
if ($AcceptComfyModelLicense) { $arguments += "-AcceptComfyModelLicense" }
if ($SkipInstall) { $arguments += "-SkipInstall" }
if ($SkipModelPull) { $arguments += "-SkipModelPull" }
$setup = Start-Process powershell -ArgumentList $arguments -Wait -PassThru
if ($setup.ExitCode -ne 0) { throw "Initial local production setup failed." }

& $StopManual -KeepDatabase
$taskArgs = @{}
if ($ExposeWithNgrok) { $taskArgs["ExposeWithNgrok"] = $true }
& $InstallTask @taskArgs
Write-Host "Always-on deployment completed." -ForegroundColor Green
Write-Host "Creator Studio: http://127.0.0.1:8000/"
Write-Host "Operator keys: .runtime\operator-keys.json"
Write-Host "Supervisor status: .runtime\supervisor-heartbeat.json"
