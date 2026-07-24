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
$InstanceLock = Join-Path $Runtime "always-on-supervisor.lock"
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "logs") | Out-Null

$lockStream = $null
try {
  $lockStream = [System.IO.File]::Open(
    $InstanceLock,
    [System.IO.FileMode]::OpenOrCreate,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
  )
} catch [System.IO.IOException] {
  Write-Host "Another always-on Content Automation supervisor already owns this runtime."
  exit 0
}

function Start-CoreSupervisor {
  $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $CoreSupervisor, "-ApiPort", [string]$ApiPort, "-PostgresPort", [string]$PostgresPort)
  if ($ExposeWithNgrok) { $arguments += "-ExposeWithNgrok" }
  return Start-Process powershell -ArgumentList $arguments -WorkingDirectory $Root -WindowStyle Hidden -PassThru
}

function Start-Continuation {
  return Start-Process -FilePath $Python `
    -ArgumentList @("-m", "src.operations.always_on_continuation", "--interval-seconds", "30", "--limit", "2") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $Runtime "logs\continuation.log") `
    -RedirectStandardError (Join-Path $Runtime "logs\continuation.error.log") `
    -PassThru
}

$core = $null
$continuation = $null
$nextContinuationStart = Get-Date
try {
  $core = Start-CoreSupervisor
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
  if ($null -ne $core -and -not $core.HasExited) {
    Stop-Process -Id $core.Id -Force -ErrorAction SilentlyContinue
  }
  if ($null -ne $lockStream) {
    $lockStream.Dispose()
  }
  Remove-Item $InstanceLock -Force -ErrorAction SilentlyContinue
}

if ($null -eq $core) { exit 1 }
exit $core.ExitCode
