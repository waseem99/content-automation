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
$EnvPath = Join-Path $Root ".env.local"
$CoreSupervisor = Join-Path $PSScriptRoot "supervise_local_production.ps1"
$StopMarker = Join-Path $Runtime "stop.request"
$InstanceLock = Join-Path $Runtime "always-on-supervisor.lock"
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "logs") | Out-Null

function Import-LocalEnvironment {
  if (-not (Test-Path -LiteralPath $EnvPath)) { return }
  foreach ($line in Get-Content -LiteralPath $EnvPath) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
    $parts = $trimmed.Split("=", 2)
    [Environment]::SetEnvironmentVariable([string]$parts[0], [string]$parts[1], "Process")
  }
}

Import-LocalEnvironment

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

function Start-P114VideoWorker {
  return Start-Process -FilePath $Python `
    -ArgumentList @("-m", "src.operations.p114_local_video_worker", "--poll-seconds", "3") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $Runtime "logs\p114-local-video-worker.log") `
    -RedirectStandardError (Join-Path $Runtime "logs\p114-local-video-worker.error.log") `
    -PassThru
}

$core = $null
$continuation = $null
$localVideoWorker = $null
$nextContinuationStart = Get-Date
$nextVideoWorkerStart = Get-Date
$localVideoEnabled = $env:P114_LOCAL_VIDEO_ENABLED -match '^(1|true|yes|on)$'
try {
  $core = Start-CoreSupervisor
  while (-not $core.HasExited) {
    if (Test-Path $StopMarker) {
      if ($null -ne $continuation -and -not $continuation.HasExited) {
        Stop-Process -Id $continuation.Id -Force -ErrorAction SilentlyContinue
        $continuation = $null
      }
      if ($null -ne $localVideoWorker -and -not $localVideoWorker.HasExited) {
        Stop-Process -Id $localVideoWorker.Id -Force -ErrorAction SilentlyContinue
        $localVideoWorker = $null
      }
      Start-Sleep -Seconds 1
      continue
    }
    if (($null -eq $continuation -or $continuation.HasExited) -and (Get-Date) -ge $nextContinuationStart) {
      $continuation = Start-Continuation
      $nextContinuationStart = (Get-Date).AddSeconds(10)
    }
    if ($localVideoEnabled -and ($null -eq $localVideoWorker -or $localVideoWorker.HasExited) -and (Get-Date) -ge $nextVideoWorkerStart) {
      $localVideoWorker = Start-P114VideoWorker
      $nextVideoWorkerStart = (Get-Date).AddSeconds(20)
    }
    Start-Sleep -Seconds 3
  }
} finally {
  if ($null -ne $localVideoWorker -and -not $localVideoWorker.HasExited) {
    Stop-Process -Id $localVideoWorker.Id -Force -ErrorAction SilentlyContinue
  }
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
