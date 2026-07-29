[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [switch]$AcknowledgeWanApache2License,
  [string]$ComfyUIRoot = "",
  [string]$ComfyUIBaseUrl = "http://127.0.0.1:8188",
  [string]$TaskName = "ContentAutomationLocal"
)

$ErrorActionPreference = "Stop"
if (-not $AcknowledgeWanApache2License) {
  throw "Activation requires explicit Wan2.2 Apache-2.0 license acknowledgement."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$EnvPath = Join-Path $Root ".env.local"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Workflow = Join-Path $Root "deploy\p114-local-video\workflows\wan2.2-ti2v-5b-i2v-api.json"
$Stop = Join-Path $PSScriptRoot "stop_always_on_local_production.ps1"

if (-not (Test-Path -LiteralPath $EnvPath)) { throw ".env.local is missing. Deploy the workstation first." }
if (-not (Test-Path -LiteralPath $Python)) { throw "The local Python environment is missing. Deploy the workstation first." }
if (-not (Test-Path -LiteralPath $Workflow)) { throw "The reviewed P114 Wan workflow is missing." }

function Read-DotEnv([string]$Path) {
  $values = [ordered]@{}
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
    $parts = $trimmed.Split("=", 2)
    $values[$parts[0]] = $parts[1]
  }
  return $values
}

function Write-DotEnv([System.Collections.IDictionary]$Values, [string]$Path) {
  [IO.File]::WriteAllLines(
    $Path,
    [string[]]@($Values.Keys | ForEach-Object { "$_=$($Values[$_])" }),
    (New-Object Text.UTF8Encoding($false))
  )
}

$values = Read-DotEnv $EnvPath
if (-not $ComfyUIRoot) {
  $ComfyUIRoot = if ($values.Contains("P114_COMFYUI_ROOT") -and $values["P114_COMFYUI_ROOT"]) {
    [string]$values["P114_COMFYUI_ROOT"]
  } else {
    "ComfyUI"
  }
}
if (-not [IO.Path]::IsPathRooted($ComfyUIRoot)) { $ComfyUIRoot = Join-Path $Root $ComfyUIRoot }
$ComfyUIRoot = (Resolve-Path $ComfyUIRoot).Path

$files = @(
  [ordered]@{ role = "diffusion_model"; relative_path = "models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" },
  [ordered]@{ role = "text_encoder"; relative_path = "models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" },
  [ordered]@{ role = "vae"; relative_path = "models/vae/wan2.2_vae.safetensors" }
)
foreach ($item in $files) {
  $path = Join-Path $ComfyUIRoot ($item.relative_path.Replace("/", "\"))
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required Wan model file is missing: $path"
  }
  $item.sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

try {
  $stats = Invoke-RestMethod -Uri "$($ComfyUIBaseUrl.TrimEnd('/'))/system_stats" -TimeoutSec 10
  if (-not $stats) { throw "No ComfyUI system statistics returned." }
  foreach ($node in @("Wan22ImageToVideoLatent", "CreateVideo", "SaveVideo")) {
    $info = Invoke-RestMethod -Uri "$($ComfyUIBaseUrl.TrimEnd('/'))/object_info/$node" -TimeoutSec 10
    if (-not $info.$node) { throw "Required ComfyUI node is unavailable: $node" }
  }
} catch {
  throw "ComfyUI is not ready for the P114 Wan workflow: $($_.Exception.Message)"
}

$values["P114_LOCAL_VIDEO_ENABLED"] = "true"
$values["P114_LOCAL_VIDEO_WORKER_OPERATOR_ID"] = "p114-local-video-worker"
$values["P114_LOCAL_VIDEO_WORKER_LEASE_SECONDS"] = "1800"
$values["P114_COMFYUI_BASE_URL"] = $ComfyUIBaseUrl.TrimEnd("/")
$values["P114_COMFYUI_ROOT"] = $ComfyUIRoot
$values["P114_WAN_EXECUTION_ENABLED"] = "true"
$values["P114_WAN_LICENSE_ACKNOWLEDGED"] = "true"
$values["P114_WAN_WORKFLOW_PATH"] = "deploy/p114-local-video/workflows/wan2.2-ti2v-5b-i2v-api.json"
$values["P114_WAN_MODEL_FILES_JSON"] = ($files | ConvertTo-Json -Compress)
$values["P114_HUNYUAN_EXECUTION_ENABLED"] = if ($values.Contains("P114_HUNYUAN_EXECUTION_ENABLED")) { $values["P114_HUNYUAN_EXECUTION_ENABLED"] } else { "false" }
$values["OPS_MIGRATION_HEAD"] = "0099_p114_dual_local_video_renderer.sql"
Write-DotEnv $values $EnvPath

foreach ($entry in $values.GetEnumerator()) {
  [Environment]::SetEnvironmentVariable([string]$entry.Key, [string]$entry.Value, "Process")
}

Push-Location $Root
try {
  & $Python -m src.infrastructure.database.cli migrate
  if ($LASTEXITCODE -ne 0) { throw "P114 database migration failed." }
  & $Python -m src.operations.p113_model_policy_onboarding
  if ($LASTEXITCODE -ne 0) { throw "P113 model policy onboarding failed." }
  & $Python -m src.operations.p114_renderer_onboarding
  if ($LASTEXITCODE -ne 0) { throw "P114 renderer activation failed." }
} finally {
  Pop-Location
}

& $Stop -KeepTask
Start-ScheduledTask -TaskName $TaskName

Write-Host "P114 Wan renderer activated with exact workflow and model hashes." -ForegroundColor Green
Write-Host "No model files were downloaded and no generation job was queued." -ForegroundColor Yellow
