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

function Test-ComfyUIReady {
  try {
    $health = Invoke-RestMethod -Uri "$($env:P114_COMFYUI_BASE_URL.TrimEnd('/'))/system_stats" -TimeoutSec 5
    return $null -ne $health
  } catch { return $false }
}

function Invoke-NativeQuiet([string]$FilePath, [string[]]$Arguments) {
  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    & $FilePath @Arguments 1>$null 2>$null
    return [int]$LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousPreference
  }
}

function Invoke-NativeLogged([string]$FilePath, [string[]]$Arguments, [string]$LogPath) {
  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    & $FilePath @Arguments *> $LogPath
    return [int]$LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousPreference
  }
}

function Wait-ForInfrastructure {
  while (-not (Test-Path $StopMarker)) {
    try {
      $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
      if (-not $dockerCommand) { throw "docker is not available" }
      if (-not (Test-Path $Python)) { throw "local virtual environment is not installed" }
      if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw "FFmpeg is not available" }

      $dockerExit = Invoke-NativeQuiet -FilePath $dockerCommand.Source -Arguments @("info")
      if ($dockerExit -ne 0) { throw "Docker Desktop is not ready" }

      Push-Location $Root
      try {
        $composeExit = Invoke-NativeQuiet -FilePath $dockerCommand.Source -Arguments @(
          "compose", "--env-file", $EnvPath, "-f", "compose.local.yml", "up", "-d", "postgres"
        )
        if ($composeExit -ne 0) { throw "PostgreSQL compose start failed with exit code $composeExit" }
      } finally { Pop-Location }

      $deadline = (Get-Date).AddMinutes(3)
      $ready = $false
      do {
        Start-Sleep -Seconds 3
        Push-Location $Root
        try {
          $readyExit = Invoke-NativeQuiet -FilePath $dockerCommand.Source -Arguments @(
            "compose", "--env-file", $EnvPath, "-f", "compose.local.yml", "exec", "-T",
            "postgres", "pg_isready", "-U", $env:POSTGRES_USER, "-d", $env:POSTGRES_DB
          )
          $ready = $readyExit -eq 0
        } finally { Pop-Location }
      } until ($ready -or (Get-Date) -gt $deadline -or (Test-Path $StopMarker))
      if (-not $ready) { throw "PostgreSQL did not become ready" }

      Push-Location $Root
      try {
        $migrationExit = Invoke-NativeLogged -FilePath $Python -Arguments @(
          "-m", "src.infrastructure.database.cli", "migrate"
        ) -LogPath (Join-Path $Runtime "logs\migration.log")
        if ($migrationExit -ne 0) { throw "Database migration failed with exit code $migrationExit" }

        $onboardingExit = Invoke-NativeLogged -FilePath $Python -Arguments @(
          "-m", "src.operations.local_onboarding_v2"
        ) -LogPath (Join-Path $Runtime "logs\onboarding.log")
        if ($onboardingExit -ne 0) { throw "Local onboarding failed with exit code $onboardingExit" }
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

function New-ManagedState([string]$Name, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory = $Root) {
  return [ordered]@{
    name = $Name
    file = $FilePath
    arguments = $Arguments
    working_directory = $WorkingDirectory
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
  $State.process = Start-Process -FilePath $State.file -ArgumentList $State.arguments -WorkingDirectory $State.working_directory `
    -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
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
    if ($null -ne $State.process -and $State.process.HasExited) {
      Write-SupervisorLog "$($State.name) exited with code $($State.process.ExitCode); restarting"
    }
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
$textWorker = New-ManagedState "text-audio-worker" $Python @("-m", "src.operations.local_worker_aligned", "--job-types", "script,narration", "--poll-seconds", "3")
$visualWorker = New-ManagedState "visual-worker" $Python @("-m", "src.operations.local_worker_aligned", "--job-types", "keyframe", "--poll-seconds", "3")
$previewWorker = New-ManagedState "preview-worker" $Python @("-m", "src.operations.local_worker_aligned", "--job-types", "preview", "--poll-seconds", "3")
$localVideoWorker = New-ManagedState "local-video-worker" $Python @("-m", "src.operations.local_video_worker", "--poll-seconds", "3")
$higgsfieldWorker = New-ManagedState "higgsfield-worker" $Python @("-m", "src.operations.higgsfield_worker", "--poll-seconds", "5")
$ngrok = New-ManagedState "ngrok" "ngrok" @("http", [string]$ApiPort)
$ngrokEnabled = $ExposeWithNgrok -or ($env:LOCAL_NGROK_ENABLED -match '^(1|true|yes|on)$')
$higgsfieldEnabled = $env:HIGGSFIELD_ENABLED -match '^(1|true|yes|on)$'
$localVideoEnabled = $env:P114_LOCAL_VIDEO_ENABLED -match '^(1|true|yes|on)$'
$comfyRoot = [string]$env:P114_COMFYUI_ROOT
if (-not $comfyRoot) { $comfyRoot = "D:\ComfyUI\App" }
$comfyPython = [string]$env:P114_COMFYUI_PYTHON
if (-not $comfyPython) { $comfyPython = Join-Path $comfyRoot ".venv\Scripts\python.exe" }
$comfyUri = [uri]$env:P114_COMFYUI_BASE_URL
if ($localVideoEnabled -and ($comfyUri.Scheme -ne "http" -or $comfyUri.Host -notin @("127.0.0.1", "localhost", "::1"))) {
  throw "P114_COMFYUI_BASE_URL must be a loopback HTTP endpoint."
}
$comfyUI = New-ManagedState "comfyui" $comfyPython @("main.py", "--listen", "127.0.0.1", "--port", [string]$comfyUri.Port, "--disable-auto-launch") $comfyRoot
$apiNotReadyChecks = 0
$apiStartupGraceSeconds = 300
$apiUnreadyCheckLimit = 60

try {
  while (-not (Test-Path $StopMarker)) {
    Ensure-ManagedProcess $api
    Ensure-ManagedProcess $textWorker
    Ensure-ManagedProcess $visualWorker
    Ensure-ManagedProcess $previewWorker

    $comfyReady = $false
    if ($localVideoEnabled) {
      $comfyReady = Test-ComfyUIReady
      if (-not $comfyReady) {
        if (-not (Test-Path -LiteralPath $comfyPython -PathType Leaf) -or -not (Test-Path -LiteralPath (Join-Path $comfyRoot "main.py") -PathType Leaf)) {
          throw "P114 is enabled but the configured ComfyUI installation is unavailable."
        }
        Ensure-ManagedProcess $comfyUI
        Start-Sleep -Seconds 1
        $comfyReady = Test-ComfyUIReady
      }
      if ($comfyReady) {
        Ensure-ManagedProcess $localVideoWorker
      } else {
        Stop-ManagedProcess $localVideoWorker
      }
    }

    if ($higgsfieldEnabled) {
      if (Get-Command higgsfield -ErrorAction SilentlyContinue) {
        Ensure-ManagedProcess $higgsfieldWorker
      } elseif ((Get-Date) -ge $higgsfieldWorker.next_start) {
        Write-SupervisorLog "Higgsfield enabled but official CLI is not on PATH"
        $higgsfieldWorker.next_start = (Get-Date).AddMinutes(5)
      }
    }

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
      if ($apiNotReadyChecks -ge $apiUnreadyCheckLimit -and (Get-Date) -ge $api.started_at.AddSeconds($apiStartupGraceSeconds)) {
        Write-SupervisorLog "API process stayed unready for $apiStartupGraceSeconds seconds; forcing restart"
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
        preview_worker = Process-Snapshot $previewWorker
        comfyui = Process-Snapshot $comfyUI
        local_video_worker = Process-Snapshot $localVideoWorker
        higgsfield_worker = Process-Snapshot $higgsfieldWorker
      }
      local_video = [ordered]@{
        enabled = [bool]$localVideoEnabled
        comfyui_ready = [bool]$comfyReady
        comfyui_base_url = [string]$env:P114_COMFYUI_BASE_URL
        external_fee_possible = $false
        automatic_approval = $false
        automatic_publishing = $false
      }
      higgsfield = [ordered]@{
        enabled = [bool]$higgsfieldEnabled
        external_fee_possible = [bool]$higgsfieldEnabled
        automatic_spend_approval = $false
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
  Stop-ManagedProcess $higgsfieldWorker
  Stop-ManagedProcess $localVideoWorker
  Stop-ManagedProcess $comfyUI
  Stop-ManagedProcess $previewWorker
  Stop-ManagedProcess $visualWorker
  Stop-ManagedProcess $textWorker
  Stop-ManagedProcess $api
  Remove-Item $SupervisorPid -Force -ErrorAction SilentlyContinue
  Remove-Item $StopMarker -Force -ErrorAction SilentlyContinue
  Write-SupervisorLog "Supervisor stopped"
}
