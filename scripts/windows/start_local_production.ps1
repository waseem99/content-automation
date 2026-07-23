[CmdletBinding()]
param(
  [int]$ApiPort = 8000,
  [int]$PostgresPort = 5434,
  [switch]$SkipInstall,
  [switch]$SkipModelPull,
  [switch]$EnableComfyUI,
  [switch]$AcceptComfyModelLicense,
  [switch]$ExposeWithNgrok
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$EnvPath = Join-Path $Root ".env.local"
$TemplatePath = Join-Path $Root "config\local.env.example"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Pip = Join-Path $Root ".venv\Scripts\pip.exe"
New-Item -ItemType Directory -Force -Path $Runtime, (Join-Path $Runtime "logs"), (Join-Path $Runtime "artifacts"), (Join-Path $Runtime "backups") | Out-Null

function New-Secret([int]$Bytes = 32) {
  $buffer = New-Object byte[] $Bytes
  $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
  try { $generator.GetBytes($buffer) } finally { $generator.Dispose() }
  return ([Convert]::ToBase64String($buffer)).TrimEnd("=").Replace("+", "-").Replace("/", "_")
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

function Write-DotEnv([System.Collections.IDictionary]$Values, [string]$Path) {
  $content = foreach ($key in $Values.Keys) { "$key=$($Values[$key])" }
  [IO.File]::WriteAllLines($Path, $content, (New-Object Text.UTF8Encoding($false)))
}

function Refresh-ProcessPath {
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machine;$user"
}

if (-not (Test-Path $EnvPath)) {
  $values = Read-DotEnv $TemplatePath
  $values["POSTGRES_PORT"] = [string]$PostgresPort
  $values["LOCAL_API_PORT"] = [string]$ApiPort
  $password = New-Secret 24
  $values["POSTGRES_PASSWORD"] = $password
  $values["DATABASE_URL"] = "postgresql://postgres:$password@127.0.0.1:$PostgresPort/content_automation"
  $keys = [ordered]@{}
  $keys[(New-Secret)] = "local-admin"
  $keys[(New-Secret)] = "local-producer"
  $keys[(New-Secret)] = "local-reviewer"
  $keys[(New-Secret)] = "local-publisher"
  $values["OPERATOR_API_KEYS_JSON"] = ($keys | ConvertTo-Json -Compress)
  Write-DotEnv $values $EnvPath
  $safeKeyFile = Join-Path $Runtime "operator-keys.json"
  $readable = [ordered]@{}
  foreach ($entry in $keys.GetEnumerator()) { $readable[$entry.Value] = $entry.Key }
  $readable | ConvertTo-Json | Set-Content -LiteralPath $safeKeyFile -Encoding utf8
  Write-Host "Created local configuration and operator keys at $safeKeyFile" -ForegroundColor Green
}

$envValues = Read-DotEnv $EnvPath
$envValues["POSTGRES_PORT"] = [string]$PostgresPort
$envValues["LOCAL_API_PORT"] = [string]$ApiPort
if ($ExposeWithNgrok) { $envValues["LOCAL_NGROK_ENABLED"] = "true" }
Write-DotEnv $envValues $EnvPath
foreach ($entry in $envValues.GetEnumerator()) {
  [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, "Process")
}

foreach ($command in "docker", "python") {
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
    throw "$command is required but was not found on PATH."
  }
}
docker info | Out-Null

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  if ($SkipInstall) {
    throw "FFmpeg is required for local MP4 previews and was not found on PATH."
  }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "FFmpeg is required. Install the Gyan.FFmpeg package or place ffmpeg on PATH, then rerun."
  }
  Write-Host "Installing FFmpeg for deterministic local MP4 previews..." -ForegroundColor Cyan
  & winget install --id Gyan.FFmpeg --exact --silent --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) { throw "FFmpeg installation failed." }
  Refresh-ProcessPath
  if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "FFmpeg installed but is not visible in this shell. Open a new elevated PowerShell and rerun."
  }
}

Push-Location $Root
try {
  docker compose --env-file $EnvPath -f compose.local.yml up -d postgres
  $deadline = (Get-Date).AddMinutes(3)
  $ready = $false
  do {
    Start-Sleep -Seconds 2
    docker compose --env-file $EnvPath -f compose.local.yml exec -T postgres pg_isready -U postgres -d content_automation *> $null
    $ready = $LASTEXITCODE -eq 0
  } until ($ready -or (Get-Date) -gt $deadline)
  if (-not $ready) { throw "PostgreSQL did not become ready." }

  if (-not (Test-Path $Python)) { python -m venv .venv }
  if (-not $SkipInstall) {
    & $Python -m pip install --upgrade pip
    & $Pip install -r requirements.txt
    & $Pip install -r video-engine\voice-requirements.txt
  }

  if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama is required. Install the Windows application, then run this script again."
  }
  try {
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 5 | Out-Null
  } catch {
    throw "Ollama is installed but its local service is not reachable on 127.0.0.1:11434."
  }
  if (-not $SkipModelPull) {
    & ollama pull $env:OLLAMA_MODEL
    if ($LASTEXITCODE -ne 0) { throw "Ollama model pull failed." }
  }

  if ($EnableComfyUI) {
    $setup = Join-Path $Root "scripts\windows\setup_p68_local_keyframe_worker.ps1"
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $setup)
    if ($AcceptComfyModelLicense) { $arguments += "-AcceptModelLicense" }
    $process = Start-Process powershell -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "ComfyUI setup failed." }
  }

  & $Python -m src.infrastructure.database.cli migrate
  if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
  & $Python -m src.operations.local_onboarding_v2
  if ($LASTEXITCODE -ne 0) { throw "Local onboarding failed." }

  $apiPid = Join-Path $Runtime "api.pid"
  $workerPid = Join-Path $Runtime "worker.pid"
  foreach ($pidFile in $apiPid, $workerPid) {
    if (Test-Path $pidFile) {
      $oldPid = [int](Get-Content $pidFile -Raw)
      if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) {
        throw "A local runtime process is already running (PID $oldPid). Use stop_local_production.ps1 first."
      }
      Remove-Item $pidFile -Force
    }
  }

  $apiLog = Join-Path $Runtime "logs\api.log"
  $apiError = Join-Path $Runtime "logs\api.error.log"
  $api = Start-Process -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "src.operator_api.entrypoint:app", "--host", "127.0.0.1", "--port", [string]$ApiPort) `
    -WorkingDirectory $Root -RedirectStandardOutput $apiLog -RedirectStandardError $apiError -PassThru
  Set-Content -LiteralPath $apiPid -Value $api.Id -Encoding ascii

  $workerLog = Join-Path $Runtime "logs\worker.log"
  $workerError = Join-Path $Runtime "logs\worker.error.log"
  $worker = Start-Process -FilePath $Python `
    -ArgumentList @("-m", "src.operations.local_worker_v2", "--poll-seconds", "3") `
    -WorkingDirectory $Root -RedirectStandardOutput $workerLog -RedirectStandardError $workerError -PassThru
  Set-Content -LiteralPath $workerPid -Value $worker.Id -Encoding ascii

  $deadline = (Get-Date).AddMinutes(2)
  $apiReady = $false
  do {
    Start-Sleep -Seconds 2
    try {
      $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/runtime/ready" -TimeoutSec 5
      $apiReady = [bool]$health.ok
    } catch { $apiReady = $false }
  } until ($apiReady -or (Get-Date) -gt $deadline)
  if (-not $apiReady) { throw "Operator API did not become ready. Inspect $apiError" }

  if ($ExposeWithNgrok) {
    if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
      throw "ngrok was requested but is not installed or not on PATH."
    }
    $ngrokPid = Join-Path $Runtime "ngrok.pid"
    $ngrokLog = Join-Path $Runtime "logs\ngrok.log"
    $ngrokError = Join-Path $Runtime "logs\ngrok.error.log"
    $ngrok = Start-Process -FilePath "ngrok" -ArgumentList @("http", [string]$ApiPort) `
      -WorkingDirectory $Root -RedirectStandardOutput $ngrokLog -RedirectStandardError $ngrokError -PassThru
    Set-Content -LiteralPath $ngrokPid -Value $ngrok.Id -Encoding ascii
  }

  Write-Host ""
  Write-Host "Creator Studio: http://127.0.0.1:$ApiPort/" -ForegroundColor Green
  Write-Host "Operator keys:  $Runtime\operator-keys.json"
  Write-Host "API log:        $apiLog"
  Write-Host "Worker log:     $workerLog"
  if ($ExposeWithNgrok) {
    Write-Host "ngrok started. Open http://127.0.0.1:4040 to copy the HTTPS forwarding URL." -ForegroundColor Yellow
  }
  Write-Host "No managed renderer or live publishing is enabled." -ForegroundColor Yellow
} finally {
  Pop-Location
}
