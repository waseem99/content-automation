[CmdletBinding()]
param(
  [string]$TaskName = "ContentAutomation-PreGeneration",
  [switch]$Disable
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$EnvPath = Join-Path $Root ".env.local"
$LogPath = Join-Path $Runtime "logs\pre-generation-service.log"
New-Item -ItemType Directory -Force -Path (Split-Path $LogPath -Parent) | Out-Null

if ($Disable) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Pre-generation task removed." -ForegroundColor Yellow
  exit 0
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
  throw "Python environment is missing: $Python"
}
if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) {
  throw "Local environment is missing: $EnvPath"
}

$launcher = Join-Path $Runtime "run-pre-generation-worker.ps1"
$launcherContent = @"
`$ErrorActionPreference = "Stop"
`$Root = '$($Root.Replace("'", "''"))'
`$EnvPath = '$($EnvPath.Replace("'", "''"))'
foreach (`$line in Get-Content -LiteralPath `$EnvPath) {
  `$trimmed = `$line.Trim()
  if (-not `$trimmed -or `$trimmed.StartsWith('#') -or -not `$trimmed.Contains('=')) { continue }
  `$parts = `$trimmed.Split('=', 2)
  [Environment]::SetEnvironmentVariable([string]`$parts[0], [string]`$parts[1], 'Process')
}
Set-Location -LiteralPath `$Root
& '$($Python.Replace("'", "''"))' -m src.operations.pre_generation_worker *>> '$($LogPath.Replace("'", "''"))'
exit `$LASTEXITCODE
"@
[IO.File]::WriteAllText($launcher, $launcherContent, (New-Object Text.UTF8Encoding($false)))

$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`"" `
  -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -RestartCount 999 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal
Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Pre-generation autopilot task installed and started: $TaskName" -ForegroundColor Green
Write-Host "Log: $LogPath"
