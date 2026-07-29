[CmdletBinding()]
param(
  [switch]$SkipComfyUI,
  [switch]$AcceptComfyModelLicense,
  [switch]$SkipInstall,
  [switch]$SkipModelPull,
  [int]$ApiPort = 8000
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$Deploy = Join-Path $PSScriptRoot "deploy_always_on_local_production.ps1"
$RemoteStatus = Join-Path $Runtime "remote-access.json"
$EnvPath = Join-Path $Root ".env.local"
$Python = Join-Path $Root ".venv\Scripts\python.exe"

function Sync-P110Environment([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return }
  $values = [ordered]@{}
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
    $parts = $trimmed.Split("=", 2)
    $values[$parts[0]] = $parts[1]
  }
  if (-not $values.Contains("KOKORO_PRIMARY_VOICE")) {
    $values["KOKORO_PRIMARY_VOICE"] = if ($values.Contains("KOKORO_VOICE") -and $values["KOKORO_VOICE"]) { [string]$values["KOKORO_VOICE"] } else { "af_heart" }
  }
  if (-not $values.Contains("KOKORO_ENERGETIC_VOICE")) { $values["KOKORO_ENERGETIC_VOICE"] = "af_bella" }
  if (-not $values.Contains("KOKORO_SERIOUS_VOICE")) { $values["KOKORO_SERIOUS_VOICE"] = "am_adam" }
  if (-not $values.Contains("LOCAL_AUTO_RESEARCH_CLAIM_LIMIT")) { $values["LOCAL_AUTO_RESEARCH_CLAIM_LIMIT"] = "8" }
  if (-not $values.Contains("LOCAL_AUTO_RESEARCH_RESULT_LIMIT")) { $values["LOCAL_AUTO_RESEARCH_RESULT_LIMIT"] = "3" }
  if (-not $values.Contains("LOCAL_AUTO_RESEARCH_MINIMUM_MATCH")) { $values["LOCAL_AUTO_RESEARCH_MINIMUM_MATCH"] = "0.45" }
  if (-not $values.Contains("P113_PILOT_TARGET_VIDEOS")) { $values["P113_PILOT_TARGET_VIDEOS"] = "3" }
  if (-not $values.Contains("P113_PILOT_TARGET_ATTEMPTS")) { $values["P113_PILOT_TARGET_ATTEMPTS"] = "30" }
  if (-not $values.Contains("P113_WAN_PROVIDER_KEY")) { $values["P113_WAN_PROVIDER_KEY"] = "wan-ai" }
  if (-not $values.Contains("P113_WAN_MODEL_KEY")) { $values["P113_WAN_MODEL_KEY"] = "Wan2.2-TI2V-5B" }
  if (-not $values.Contains("P113_HUNYUAN_PROVIDER_KEY")) { $values["P113_HUNYUAN_PROVIDER_KEY"] = "tencent-hunyuan" }
  if (-not $values.Contains("P113_HUNYUAN_MODEL_KEY")) { $values["P113_HUNYUAN_MODEL_KEY"] = "HunyuanVideo-1.5-480p-I2V-Step-Distilled" }
  $values["OPS_MIGRATION_HEAD"] = "0098_p113_pilot_video_grouping.sql"
  [IO.File]::WriteAllLines(
    $Path,
    [string[]]@($values.Keys | ForEach-Object { "$_=$($values[$_])" }),
    (New-Object Text.UTF8Encoding($false))
  )
}

Sync-P110Environment $EnvPath

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
  throw "ngrok is required. Install ngrok, run 'ngrok config add-authtoken <token>', then rerun."
}

# A configured account is required. The command reveals no token.
& ngrok config check 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "ngrok is installed but not configured. Run 'ngrok config add-authtoken <token>' first."
}

$arguments = @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-File", $Deploy,
  "-ExposeWithNgrok"
)
if (-not $SkipComfyUI) { $arguments += "-EnableComfyUI" }
if ($AcceptComfyModelLicense) { $arguments += "-AcceptComfyModelLicense" }
if ($SkipInstall) { $arguments += "-SkipInstall" }
if ($SkipModelPull) { $arguments += "-SkipModelPull" }

$deployment = Start-Process powershell -ArgumentList $arguments -WorkingDirectory $Root -Wait -PassThru
if ($deployment.ExitCode -ne 0) {
  throw "Remote Content Automation deployment failed. Inspect .runtime\logs."
}

if (-not (Test-Path -LiteralPath $Python)) {
  throw "P113 model policy onboarding could not run because the local Python environment is missing."
}
Push-Location $Root
try {
  & $Python -m src.operations.p113_model_policy_onboarding
  if ($LASTEXITCODE -ne 0) { throw "P113 model policy onboarding failed." }
} finally {
  Pop-Location
}

$deadline = (Get-Date).AddMinutes(2)
$publicUrl = $null
do {
  Start-Sleep -Seconds 2
  try {
    $localReady = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/runtime/ready" -TimeoutSec 5
    if (-not $localReady.ok) { continue }
    $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5
    $httpsTunnel = @($tunnels.tunnels | Where-Object { $_.proto -eq "https" }) | Select-Object -First 1
    if ($httpsTunnel) { $publicUrl = [string]$httpsTunnel.public_url }
  } catch {
    $publicUrl = $null
  }
} until ($publicUrl -or (Get-Date) -gt $deadline)

if (-not $publicUrl) {
  throw "The local runtime started but no HTTPS ngrok tunnel was discovered. Inspect .runtime\logs\ngrok.error.log."
}

try {
  $remoteReady = Invoke-RestMethod -Uri "$publicUrl/runtime/ready" -Headers @{ "ngrok-skip-browser-warning" = "true" } -TimeoutSec 15
  if (-not $remoteReady.ok) { throw "Remote readiness returned false." }
} catch {
  throw "The ngrok URL exists but the authenticated Creator Studio runtime is not reachable: $($_.Exception.Message)"
}

$status = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  public_url = $publicUrl
  creator_studio_url = "$publicUrl/app/dashboard"
  local_url = "http://127.0.0.1:$ApiPort/app/dashboard"
  authentication_required = $true
  exposed_service = "creator-studio-api-only"
  postgres_exposed = $false
  ollama_exposed = $false
  comfyui_exposed = $false
  artifact_directory_exposed = $false
  role_model = @("super_admin", "admin", "reviewer")
  operator_keys_path = ".runtime/operator-keys.json"
}
$status | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $RemoteStatus -Encoding utf8

Write-Host ""
Write-Host "Remote Content Automation is ready." -ForegroundColor Green
Write-Host "Creator Studio: $publicUrl/app/dashboard" -ForegroundColor Green
Write-Host "Operator keys:  $Runtime\operator-keys.json"
Write-Host "Remote status:  $RemoteStatus"
Write-Host "Share only the HTTPS Creator Studio URL and the intended user's key. Never share the Super Admin key." -ForegroundColor Yellow
