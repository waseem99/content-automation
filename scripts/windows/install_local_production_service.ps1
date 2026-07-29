[CmdletBinding()]
param(
  [string]$TaskName = "ContentAutomationLocal",
  [switch]$ExposeWithNgrok
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$Supervisor = Join-Path $PSScriptRoot "supervise_always_on_local_production.ps1"
$StopMarker = Join-Path $Runtime "stop.request"
$SupervisorPid = Join-Path $Runtime "supervisor.pid"
$Heartbeat = Join-Path $Runtime "supervisor-heartbeat.json"

if (-not (Test-Path (Join-Path $Root ".env.local"))) {
  throw "Run deploy_always_on_local_production.ps1 to create the local environment first."
}

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

function Stop-ExistingLocalRuntime {
  Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  New-Item -ItemType File -Force -Path $StopMarker | Out-Null

  $escapedRoot = [regex]::Escape($Root)
  $deadline = (Get-Date).AddSeconds(20)
  do {
    $running = @(
      Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match $escapedRoot -and
        (
          $_.CommandLine -match "supervise_always_on_local_production\.ps1" -or
          $_.CommandLine -match "supervise_local_production\.ps1"
        )
      }
    )
    if ($running.Count -eq 0) { break }
    Start-Sleep -Seconds 1
  } while ((Get-Date) -lt $deadline)

  $remainingSupervisors = @(
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $_.CommandLine -and
      $_.CommandLine -match $escapedRoot -and
      (
        $_.CommandLine -match "supervise_always_on_local_production\.ps1" -or
        $_.CommandLine -match "supervise_local_production\.ps1"
      )
    } |
    Sort-Object ProcessId -Descending
  )

  foreach ($process in $remainingSupervisors) {
    if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) {
      & taskkill.exe /PID $process.ProcessId /T /F 1>$null 2>$null
    }
  }

  # Remove only child processes whose command lines prove they belong to this repository.
  $remainingRuntimeChildren = @(
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $_.CommandLine -and
      $_.CommandLine -match $escapedRoot -and
      (
        $_.CommandLine -match "src\.operator_api\.entrypoint:app" -or
        $_.CommandLine -match "src\.operations\.local_worker_aligned" -or
        $_.CommandLine -match "src\.operations\.always_on_continuation" -or
        $_.CommandLine -match "src\.operations\.p114_local_video_worker"
      )
    } |
    Sort-Object ProcessId -Descending
  )

  foreach ($process in $remainingRuntimeChildren) {
    if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) {
      & taskkill.exe /PID $process.ProcessId /T /F 1>$null 2>$null
    }
  }

  Remove-Item $StopMarker -Force -ErrorAction SilentlyContinue
  Remove-Item $SupervisorPid -Force -ErrorAction SilentlyContinue
  Remove-Item $Heartbeat -Force -ErrorAction SilentlyContinue
}

Stop-ExistingLocalRuntime

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
