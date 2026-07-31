[CmdletBinding()]
param(
  [string]$ComfyUIRoot = "D:\ComfyUI\App",
  [string]$TaskName = "ContentAutomationLocal",
  [switch]$SkipProof,
  [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$EnvPath = Join-Path $Root ".env.local"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$StopScript = Join-Path $PSScriptRoot "stop_always_on_local_production.ps1"
$SupervisorScript = Join-Path $PSScriptRoot "supervise_always_on_local_production.ps1"
$ComfyPython = Join-Path $ComfyUIRoot ".venv\Scripts\python.exe"
$ComfyMain = Join-Path $ComfyUIRoot "main.py"
$ModelRoot = Join-Path $ComfyUIRoot "models"
$ManifestPath = Join-Path $Root "config\local-video-workflows\wan22-ti2v-5b.manifest.json"
$WorkflowRoot = Join-Path $Root "config\local-video-workflows"
$ReadinessPath = Join-Path $Runtime "p114-readiness.json"
$LogRoot = Join-Path $Runtime "logs\p114-activation"
$EnvBackup = Join-Path $Runtime ("env-before-p114-{0}.local" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$ComfyBaseUrl = "http://127.0.0.1:8188"
$TemporaryComfyProcess = $null
New-Item -ItemType Directory -Force -Path $Runtime, $LogRoot | Out-Null

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

function Write-DotEnv([System.Collections.IDictionary]$Values, [string]$Path) {
  $content = foreach ($key in $Values.Keys) { "$key=$($Values[$key])" }
  [IO.File]::WriteAllLines($Path, $content, (New-Object Text.UTF8Encoding($false)))
}

function Import-Environment([System.Collections.IDictionary]$Values) {
  foreach ($entry in $Values.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable([string]$entry.Key, [string]$entry.Value, "Process")
  }
}

function Invoke-PythonStep([string]$Name, [string[]]$Arguments) {
  $stdout = Join-Path $LogRoot "$Name.log"
  $stderr = Join-Path $LogRoot "$Name.error.log"
  Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
  Write-Host "Running $Name..." -ForegroundColor Cyan
  $process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -Wait -PassThru -NoNewWindow
  if (Test-Path -LiteralPath $stdout) { Get-Content -LiteralPath $stdout | ForEach-Object { Write-Host $_ } }
  if ($process.ExitCode -ne 0) {
    if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Tail 200 | ForEach-Object { Write-Host $_ -ForegroundColor Red } }
    throw "$Name failed with exit code $($process.ExitCode). Review $LogRoot"
  }
  return $stdout
}

function Set-P114Enabled([System.Collections.IDictionary]$Values, [bool]$Enabled) {
  $Values["P114_LOCAL_VIDEO_ENABLED"] = if ($Enabled) { "true" } else { "false" }
  Write-DotEnv $Values $EnvPath
  [Environment]::SetEnvironmentVariable("P114_LOCAL_VIDEO_ENABLED", $Values["P114_LOCAL_VIDEO_ENABLED"], "Process")
}

function Test-ComfyUIReady {
  try {
    $health = Invoke-RestMethod -Uri "$ComfyBaseUrl/system_stats" -TimeoutSec 5
    return $null -ne $health
  } catch {
    return $false
  }
}

function Start-TemporaryComfyUI {
  if (Test-ComfyUIReady) {
    Write-Host "Using the existing loopback ComfyUI process." -ForegroundColor Green
    return $null
  }

  $stdout = Join-Path $LogRoot "temporary-comfyui.log"
  $stderr = Join-Path $LogRoot "temporary-comfyui.error.log"
  Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
  Write-Host "Starting temporary loopback-only ComfyUI for validation and proof..." -ForegroundColor Cyan
  $process = Start-Process -FilePath $ComfyPython -ArgumentList @("main.py", "--listen", "127.0.0.1", "--port", "8188", "--disable-auto-launch") -WorkingDirectory $ComfyUIRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Minimized -PassThru
  $deadline = (Get-Date).AddMinutes(10)
  do {
    if ($process.HasExited) {
      if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Tail 200 | ForEach-Object { Write-Host $_ -ForegroundColor Red } }
      throw "Temporary ComfyUI exited before becoming ready."
    }
    Start-Sleep -Seconds 3
  } until ((Test-ComfyUIReady) -or (Get-Date) -gt $deadline)

  if (-not (Test-ComfyUIReady)) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    throw "ComfyUI did not become ready within ten minutes."
  }
  Write-Host "Temporary ComfyUI is ready at $ComfyBaseUrl." -ForegroundColor Green
  return $process
}

function Stop-TemporaryComfyUI([object]$Process) {
  if ($null -ne $Process -and -not $Process.HasExited) {
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    try { Wait-Process -Id $Process.Id -Timeout 30 -ErrorAction SilentlyContinue } catch {}
  }
}

function Start-AlwaysOnRuntime {
  if ($SkipRestart) { return }
  $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($task) {
    Start-ScheduledTask -TaskName $TaskName
    return
  }
  Start-Process powershell -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $SupervisorScript) -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
}

if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) { throw ".env.local is missing. Deploy local production first." }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Repository Python environment is missing: $Python" }
if (-not (Test-Path -LiteralPath $ComfyPython -PathType Leaf) -or -not (Test-Path -LiteralPath $ComfyMain -PathType Leaf)) { throw "ComfyUI is unavailable at $ComfyUIRoot" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "P114 Wan2.2 manifest is missing. Pull the merged P114 production branch first." }
if (-not (Test-Path -LiteralPath $StopScript -PathType Leaf)) { throw "Always-on stop script is missing." }

Copy-Item -LiteralPath $EnvPath -Destination $EnvBackup -Force
$values = Read-DotEnv $EnvPath
$values["P114_COMFYUI_BASE_URL"] = $ComfyBaseUrl
$values["P114_COMFYUI_ROOT"] = $ComfyUIRoot
$values["P114_COMFYUI_PYTHON"] = $ComfyPython
$values["P114_WORKFLOW_ROOT"] = $WorkflowRoot
$values["P114_MANIFEST_PATH"] = $ManifestPath
$values["P114_MODEL_ROOT"] = $ModelRoot
$values["P114_JOB_TIMEOUT_SECONDS"] = "14400"
$values["P114_MAX_ATTEMPTS"] = "2"
$values["P114_RETRY_DELAY_SECONDS"] = "20"
$values["P114_MOTION_PROMPT_SUFFIX"] = "Preserve the approved subject and composition. Add subtle natural motion and a slow controlled camera move. No cuts."
$values["LOCAL_VIDEO_WORKER_OPERATOR_ID"] = "local-video-worker"
$values["LOCAL_VIDEO_WORKER_LEASE_SECONDS"] = "1800"
$values["LOCAL_VIDEO_POLL_SECONDS"] = "3"
Set-P114Enabled $values $false
Import-Environment $values

Write-Host "Stopping the always-on runtime without deleting data or the scheduled task..." -ForegroundColor Cyan
& $StopScript -TaskName $TaskName -KeepTask

try {
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    Push-Location $Root
    try {
      & docker compose --env-file $EnvPath -f compose.local.yml up -d postgres
      if ($LASTEXITCODE -ne 0) { throw "PostgreSQL startup failed." }
      $databaseReady = $false
      $deadline = (Get-Date).AddMinutes(3)
      do {
        Start-Sleep -Seconds 3
        & docker compose --env-file $EnvPath -f compose.local.yml exec -T postgres pg_isready -U $env:POSTGRES_USER -d $env:POSTGRES_DB 1>$null 2>$null
        $databaseReady = $LASTEXITCODE -eq 0
      } until ($databaseReady -or (Get-Date) -gt $deadline)
      if (-not $databaseReady) { throw "PostgreSQL did not become ready within three minutes." }
    } finally { Pop-Location }
  }

  $TemporaryComfyProcess = Start-TemporaryComfyUI
  Invoke-PythonStep "database-migrate" @("-m", "src.infrastructure.database.cli", "migrate") | Out-Null
  Invoke-PythonStep "local-onboarding" @("-m", "src.operations.local_onboarding_v2") | Out-Null

  Set-P114Enabled $values $true
  Import-Environment $values

  $proofResult = $null
  if ($SkipProof) {
    Invoke-PythonStep "p114-onboard" @("-m", "src.operations.p114_wan22_activation", "onboard") | Out-Null
  } else {
    Write-Host "Running one repository-controlled P87 -> P114 proof. This may take a long time on an 8 GB GPU." -ForegroundColor Yellow
    $proofLog = Invoke-PythonStep "p114-proof" @("-m", "src.operations.p114_wan22_activation", "proof")
    $lastLine = Get-Content -LiteralPath $proofLog | Where-Object { $_.Trim() } | Select-Object -Last 1
    if ($lastLine) {
      try { $proofResult = $lastLine | ConvertFrom-Json } catch { $proofResult = @{ raw = $lastLine } }
    }
  }

  Stop-TemporaryComfyUI $TemporaryComfyProcess
  $TemporaryComfyProcess = $null
  Start-AlwaysOnRuntime

  $readiness = [ordered]@{
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    ok = $true
    p114_enabled = $true
    comfyui_base_url = $ComfyBaseUrl
    comfyui_root = $ComfyUIRoot
    manifest_path = $ManifestPath
    model_root = $ModelRoot
    proof = $proofResult
    external_fee_possible = $false
    automatic_approval = $false
    automatic_publishing = $false
    env_backup = $EnvBackup
  }
  $readiness | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReadinessPath -Encoding utf8

  Write-Host ""
  Write-Host "P114 WAN2.2 PRODUCTION ACTIVATION COMPLETE" -ForegroundColor Green
  Write-Host "Always-on generation is enabled for approved selected keyframes." -ForegroundColor Green
  Write-Host "Readiness evidence: $ReadinessPath"
  Write-Host "No content was auto-approved or published." -ForegroundColor Yellow
} catch {
  Stop-TemporaryComfyUI $TemporaryComfyProcess
  Set-P114Enabled $values $false
  Import-Environment $values
  Start-AlwaysOnRuntime
  [ordered]@{
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    ok = $false
    p114_enabled = $false
    error = "{0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message
    log_root = $LogRoot
    env_backup = $EnvBackup
  } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReadinessPath -Encoding utf8
  throw
}
