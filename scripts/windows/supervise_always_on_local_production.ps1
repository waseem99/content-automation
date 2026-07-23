[CmdletBinding()]
param(
  [int]$ApiPort = 8000,
  [int]$PostgresPort = 5434,
  [switch]$ExposeWithNgrok
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$CoreSupervisor = Join-Path $PSScriptRoot "supervise_local_production.ps1"
$StopMarker = Join-Path $Runtime "stop.request"
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "logs") | Out-Null

function Start-CoreSupervisor {
  $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $CoreSupervisor, "-ApiPort", [string]$ApiPort, "-PostgresPort", [string]$PostgresPort)
  if ($ExposeWithNgrok) { $arguments += "-ExposeWithNgrok" }
  return Start-Process powershell -ArgumentList $arguments -WorkingDirectory $Root -PassThru
}

function Start-Continuation {
  return Start-Process -FilePath $Python `
    -ArgumentList @("-m", "src.operations.always_on_continuation", "--interval-seconds", "30", "--limit", "2") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput (Join-Path $Runtime "logs\continuation.log") `
    -RedirectStandardError (Join-Path $Runtime "logs\continuation.error.log") `
    -PassThru
}

$core = Start-CoreSupervisor
$continuation = $null
$nextContinuationStart = Get-Date
try {
  while (-not $core.HasExited) {
    if (Test-Path $StopMarker) { break }
    if (($null -eq $continuation -or $continuation.HasExited) -and (Get-Date) -ge $nextContinuationStart) {
      $continuation = Start-Continuation
      $nextContinuationStart = (Get-Date).AddSeconds(10)
    }
    Start-Sleep -Seconds 3
  }
} finally {
  if ($null -ne $continuation -and -not $continuation.HasExited) {
    Stop-Process -Id $continuation.Id -Force -ErrorAction SilentlyContinue
  }
  if (-not $core.HasExited) {
    Stop-Process -Id $core.Id -Force -ErrorAction SilentlyContinue
  }
}
exit $core.ExitCode
