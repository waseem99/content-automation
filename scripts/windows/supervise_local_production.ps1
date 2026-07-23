[CmdletBinding()]
param(
  [int]$ApiPort = 8000,
  [int]$PostgresPort = 5434,
  [switch]$ExposeWithNgrok
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$EnvPath = Join-Path $Root ".env.local"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$StopMarker = Join-Path $Runtime "stop.request"
$SupervisorPid = Join-Path $Runtime "supervisor.pid"
$Heartbeat = Join-Path $Runtime "supervisor-heartbeat.json"
$SupervisorLog = Join-Path $Runtime "logs\supervisor.log"
New-Item -ItemType Directory -Force -Path $Runtime, (Join-Path $Runtime "logs"), (Join-Path $Runtime "artifacts"), (Join-Path $Runtime "backups") | Out-Null
Remove-Item $StopMarker -Force -ErrorAction SilentlyContinue
Set-Content -LiteralPath $SupervisorPid -Value $PID -Encoding ascii

function Write-SupervisorLog([string]$Message) {
  $line = "{0:o} {1}" -f (Get-Date), $Message
  Add-Content -LiteralPath $SupervisorLog -Value $line -Encoding utf8
}

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

function Import-LocalEnvironment {
  if (-not (Test-Path $EnvPath)) { throw ".env.local is missing. Run deploy_always_on_local_production.ps1." }
  $values = Read-DotEnv $EnvPath
  $values["POSTGRES_PORT"] = [string]$PostgresPort
  $values["LOCAL_API_PORT"] = [string]$ApiPort
  foreach ($entry in $values.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
  }
}

function Test-ApiReady {
  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/runtime/ready" -TimeoutSec 4
    return [bool]$health.ok
  } catch { return $false }
}

function Wait-ForInfrastructure {
  while (-not (Test-Path $StopMarker)) {
    try {
      if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "docker is not available" }
      if (-not (Test-Path $Python)) { throw "local virtual environment is not installed" }
      docker info *> $null
      if ($LASTEXITCODE -ne 0) { throw "Docker Desktop is not ready" }
      Push-Location $Root
      try {
        docker compose --env-file $EnvPath -f compose.local.yml up -d postgres *> $null
        if ($LASTEXITCODE -ne 0) { throw "PostgreSQL compose start failed" }
      } finally { Pop-Location }
      $deadline = (Get-Date).AddMinutes(3)
      $ready = $false
      do {
        Start-Sleep -Seconds 3
        Push-Location $Root
        try {
          docker compose --env-file $EnvPath -f compose.local.yml exec -T postgres pg_isready -U $env:POSTGRES_USER -d $env:POSTGRES_DB *> $null
          $ready = $LASTEXITCODE -eq 0
        } finally { Pop-Location }
      } until ($ready -or (Get-Date) -gt $deadline -or (Test-Path $StopMarker))
      if (-not $ready) { throw "PostgreSQL did not become ready" }
      Push-Location $Root
      try {
        & $Python -m src.infrastructure.database.cli migrate *> (Join-Path $Runtime "logs\migration.log")
        if ($LASTEXITCODE -ne 0) { throw "Database migration failed" }
        & $Python -m src.operations.local_onboarding_v2 *> (Join-Path $Runtime "logs\onboarding.log")
        if ($LASTEXITCODE -ne 0) { throw "Local onboarding failed" }
      } finally { Pop-Location }
      return
    } catch {
      Write-SupervisorLog "Infrastructure wait: $($_.Exception.Message)"
      Start-Sleep -Seconds 15
    }
  }
}

function Rotate-Log([string]$Path) {
  if ((Test-Path $Path) -and ((Get-Item $Path).Length -gt 20971520)) {
    $archive = "$Path.$((Get-Date).ToString('yyyyMMdd-HHmmss'))"
    Move-Item -LiteralPath $Path -Destination $archive -Force
  }
}

function New-ManagedState([string]$Name, [string]$FilePath, [string[]]$Arguments) {
  return [ordered]@{
    name = $Name
    file = $FilePath
    arguments = $Arguments
    process = $null
    restart_count = 0
    next_start = Get-Date
    started_at = $null
  }
}

function Start-ManagedProcess($State) {
  $out = Join-Path $Runtime "logs\$($State.name).log"
  $err = Join-Path $Runtime "logs\$($State.name).error.log"
  Rotate-Log $out
  Rotate-Log $err
  Write-SupervisorLog "Starting $($State.name)"
  $State.process = Start-Process -FilePath $State.file -ArgumentList $State.arguments -WorkingDirectory $Root `
    -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  $State.started_at = Get-Date
  $State.restart_count = [int]$State.restart_count + 1
  $delay = [Math]::Min(60, [Math]::Pow(2, [Math]::Min([int]$State.restart_count, 6)))
  $State.next_start = (Get-Date).AddSeconds($delay)
}

function Stop-ManagedProcess($State) {
  if ($null -ne $State.process -and -not $State.process.HasExited) {
    Write-SupervisorLog "Stopping $($State.name) PID $($State.process.Id)"
    Stop-Process -Id $State.process.Id -Force -ErrorAction SilentlyContinue
  }
  $State.process = $null
}

function Ensure-ManagedProcess($State) {
  $now = Get-Date
  $stopped = $null -eq $State.process -or $State.process.HasExited
  if ($stopped -and $now -ge $State.next_start) {
    Start-ManagedProcess $State
    return
  }
  if (-not $stopped -and $null -ne $State.started_at -and $now -ge $State.started_at.AddMinutes(2)) {
    $State.restart_count = 0
  }
}

function Process-Snapshot($State) {
  $running = $null -ne $State.process -and -not $State.process.HasExited
  $pidValue = $null
  if ($running) { $pidValue = $State.process.Id }
  return [ordered]@{
    running = [bool]$running
    pid = $pidValue
    restart_count = [int]$State.restart_count
  }
}

Import-LocalEnvironment
Write-SupervisorLog "Supervisor started PID $PID"
Wait-ForInfrastructure

$api = New-ManagedState "api" $Python @("-m", "uvicorn", "src.operator_api.entrypoint:app", "--host", "127.0.0.1", "--port", [string]$ApiPort)
$textWorker = New-ManagedState "text-audio-worker" $Python @("-m", "src.operations.local_worker_v2", "--job-types", "script,narration", "--poll-seconds", "3")
$visualWorker = New-ManagedState "visual-worker" $Python @("-m", "src.operations.local_worker_v2", "--job-types", "keyframe", "--poll-seconds", "3")
$ngrok = New-ManagedState "ngrok" "ngrok" @("http", [string]$ApiPort)
$ngrokEnabled = $ExposeWithNgrok -or ($env:LOCAL_NGROK_ENABLED -match '^(1|true|yes|on)$')
$apiNotReadyChecks = 0

try {
  while (-not (Test-Path $StopMarker)) {
    Ensure-ManagedProcess $api
    Ensure-ManagedProcess $textWorker
    Ensure-ManagedProcess $visualWorker

    if ($ngrokEnabled) {
      if (Get-Command ngrok -ErrorAction SilentlyContinue) {
        Ensure-ManagedProcess $ngrok
      } elseif ((Get-Date) -ge $ngrok.next_start) {
        Write-SupervisorLog "ngrok enabled but executable is not on PATH"
        $ngrok.next_start = (Get-Date).AddMinutes(5)
      }
    }

    $apiReady = Test-ApiReady
    if ($null -ne $api.process -and -not $api.process.HasExited -and -not $apiReady) {
      $apiNotReadyChecks++
      if ($apiNotReadyChecks -ge 12 -and (Get-Date) -ge $api.started_at.AddMinutes(1)) {
        Write-SupervisorLog "API process stayed unready; forcing restart"
        Stop-ManagedProcess $api
        $api.next_start = (Get-Date).AddSeconds(5)
        $apiNotReadyChecks = 0
      }
    } else {
      $apiNotReadyChecks = 0
    }

    $state = [ordered]@{
      timestamp = (Get-Date).ToUniversalTime().ToString("o")
      supervisor_pid = $PID
      api_ready = [bool]$apiReady
      processes = [ordered]@{
        api = Process-Snapshot $api
        text_audio_worker = Process-Snapshot $textWorker
        visual_worker = Process-Snapshot $visualWorker
      }
      ngrok = [ordered]@{
        enabled = [bool]$ngrokEnabled
        process = Process-Snapshot $ngrok
      }
      automatic_approval = $false
      live_publishing = $false
    }
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Heartbeat -Encoding utf8
    Start-Sleep -Seconds 5
  }
} finally {
  Stop-ManagedProcess $ngrok
  Stop-ManagedProcess $visualWorker
  Stop-ManagedProcess $textWorker
  Stop-ManagedProcess $api
  Remove-Item $SupervisorPid -Force -ErrorAction SilentlyContinue
  Remove-Item $StopMarker -Force -ErrorAction SilentlyContinue
  Write-SupervisorLog "Supervisor stopped"
}
