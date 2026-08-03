[CmdletBinding()]
param(
  [int]$PollSeconds = 5
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$EnvPath = Join-Path $Root ".env.local"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$StopMarker = Join-Path $Runtime "provider-workers.stop"
$Heartbeat = Join-Path $Runtime "provider-workers-heartbeat.json"
$SupervisorPid = Join-Path $Runtime "provider-workers.pid"
$SupervisorLog = Join-Path $Runtime "logs\provider-workers-supervisor.log"
New-Item -ItemType Directory -Force -Path $Runtime, (Join-Path $Runtime "logs") | Out-Null
Remove-Item $StopMarker -Force -ErrorAction SilentlyContinue
Set-Content -LiteralPath $SupervisorPid -Value $PID -Encoding ascii

function Read-DotEnv([string]$Path) {
  $result = [ordered]@{}
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
    $parts = $trimmed.Split("=", 2)
    $result[$parts[0]] = $parts[1]
  }
  return $result
}

function Import-Environment {
  if (-not (Test-Path -LiteralPath $EnvPath)) { throw ".env.local is missing." }
  foreach ($entry in (Read-DotEnv $EnvPath).GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
  }
}

function Test-Flag([string]$Name) {
  $value = [Environment]::GetEnvironmentVariable($Name, "Process")
  return $value -match '^(1|true|yes|on)$'
}

function Write-Log([string]$Message) {
  Add-Content -LiteralPath $SupervisorLog -Value ("{0:o} {1}" -f (Get-Date), $Message) -Encoding utf8
}

function New-State([string]$Provider) {
  return [ordered]@{
    provider = $Provider
    process = $null
    restart_count = 0
    next_start = Get-Date
    started_at = $null
  }
}

function Start-Worker($State) {
  $provider = [string]$State.provider
  $out = Join-Path $Runtime "logs\$provider-worker.log"
  $err = Join-Path $Runtime "logs\$provider-worker.error.log"
  Write-Log "Starting $provider worker"
  $State.process = Start-Process -FilePath $Python `
    -ArgumentList @("-m", "src.operations.provider_managed_worker", "--provider", $provider, "--poll-seconds", [string]$PollSeconds) `
    -WorkingDirectory $Root -WindowStyle Hidden `
    -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  $State.started_at = Get-Date
  $State.restart_count = [int]$State.restart_count + 1
  $delay = [Math]::Min(60, [Math]::Pow(2, [Math]::Min([int]$State.restart_count, 6)))
  $State.next_start = (Get-Date).AddSeconds($delay)
}

function Stop-Worker($State) {
  if ($null -ne $State.process -and -not $State.process.HasExited) {
    Stop-Process -Id $State.process.Id -Force -ErrorAction SilentlyContinue
  }
  $State.process = $null
}

function Ensure-Worker($State, [bool]$Enabled, [bool]$CredentialPresent) {
  if (-not $Enabled -or -not $CredentialPresent) {
    Stop-Worker $State
    return
  }
  $stopped = $null -eq $State.process -or $State.process.HasExited
  if ($stopped -and (Get-Date) -ge $State.next_start) {
    if ($null -ne $State.process -and $State.process.HasExited) {
      Write-Log "$($State.provider) worker exited with code $($State.process.ExitCode); restarting"
    }
    Start-Worker $State
    return
  }
  if (-not $stopped -and $null -ne $State.started_at -and (Get-Date) -ge $State.started_at.AddMinutes(2)) {
    $State.restart_count = 0
  }
}

function Snapshot($State) {
  $running = $null -ne $State.process -and -not $State.process.HasExited
  return [ordered]@{
    enabled = $true
    running = [bool]$running
    pid = if ($running) { $State.process.Id } else { $null }
    restart_count = [int]$State.restart_count
  }
}

Import-Environment
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "The local Python environment is missing." }
if (-not (Test-Flag "PROVIDER_PAID_EXECUTION_ENABLED")) {
  throw "Provider execution is disabled. Run setup_provider_first_rendering.ps1 with -EnablePaidExecution after approving budgets."
}

$fal = New-State "fal"
$vidu = New-State "vidu"
Write-Log "Provider worker supervisor started PID $PID"

try {
  while (-not (Test-Path -LiteralPath $StopMarker)) {
    Import-Environment
    $master = Test-Flag "PROVIDER_PAID_EXECUTION_ENABLED"
    $falEnabled = $master -and (Test-Flag "FAL_RENDERER_ENABLED")
    $viduEnabled = $master -and (Test-Flag "VIDU_RENDERER_ENABLED")
    $falKeyPresent = -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("FAL_KEY", "Process"))
    $viduKeyPresent = -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("VIDU_API_KEY", "Process"))

    Ensure-Worker $fal $falEnabled $falKeyPresent
    Ensure-Worker $vidu $viduEnabled $viduKeyPresent

    $status = [ordered]@{
      timestamp = (Get-Date).ToUniversalTime().ToString("o")
      supervisor_pid = $PID
      paid_execution_enabled = [bool]$master
      providers = [ordered]@{
        fal = (Snapshot $fal)
        vidu = (Snapshot $vidu)
      }
      credentials = [ordered]@{
        fal_present = [bool]$falKeyPresent
        vidu_present = [bool]$viduKeyPresent
      }
      automatic_spend_approval = $false
      automatic_creative_approval = $false
      automatic_publishing = $false
    }
    $status.providers.fal.enabled = [bool]$falEnabled
    $status.providers.vidu.enabled = [bool]$viduEnabled
    $status | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Heartbeat -Encoding utf8
    Start-Sleep -Seconds 5
  }
} finally {
  Stop-Worker $fal
  Stop-Worker $vidu
  Remove-Item $SupervisorPid -Force -ErrorAction SilentlyContinue
  Write-Log "Provider worker supervisor stopped"
}
