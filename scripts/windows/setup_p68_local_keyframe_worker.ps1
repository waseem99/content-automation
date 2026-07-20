param(
    [string]$DataRoot = "D:\content-automation-data\p68-keyframe-worker",
    [switch]$AcceptModelLicense,
    [switch]$SkipImageBuild
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$deployRoot = Join-Path $repoRoot "deploy\p68-local-keyframe-worker"
$downloadScript = Join-Path $PSScriptRoot "download_p68_sdxl_preview_model.ps1"
$modelName = "sd_xl_base_1.0.safetensors"
$modelPath = Join-Path (Join-Path $DataRoot "models") $modelName
$envPath = Join-Path $DataRoot "local-keyframe-worker.env"
$comfyUiRef = "v0.3.26"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required and was not found."
}

Write-Host "Checking Docker GPU passthrough..." -ForegroundColor Cyan
& docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
if ($LASTEXITCODE -ne 0) {
    throw "Docker cannot access the NVIDIA GPU."
}

foreach ($folder in ("models", "input", "output", "artifacts")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $DataRoot $folder) | Out-Null
}

if (-not (Test-Path $modelPath)) {
    if (-not $AcceptModelLicense) {
        throw "The SDXL preview checkpoint is missing. Re-run with -AcceptModelLicense after reviewing the model licence."
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $downloadScript -DataRoot $DataRoot -AcceptModelLicense
    if ($LASTEXITCODE -ne 0) {
        throw "The reviewed checkpoint download did not complete."
    }
}

$dockerDataRoot = $DataRoot.Replace('\', '/')
$envContent = @"
COMFYUI_REF=$comfyUiRef
P68_KEYFRAME_MODEL_DIR=$dockerDataRoot/models
P68_KEYFRAME_OUTPUT_DIR=$dockerDataRoot/output
P68_KEYFRAME_INPUT_DIR=$dockerDataRoot/input
P68_KEYFRAME_PORT=8188
P68_KEYFRAME_CHECKPOINT=$modelName
COMFYUI_EXTRA_ARGS=--lowvram
P68_KEYFRAME_BASE_URL=http://127.0.0.1:8188
P68_KEYFRAME_MODEL_LICENSE_TYPE=CreativeML-Open-RAIL++-M
P68_KEYFRAME_MODEL_LICENSE_URL=https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md
P68_KEYFRAME_GPU_HOURLY_USD=0.00
P68_KEYFRAME_SOFT_CAP_USD=0.00
P68_KEYFRAME_HARD_CAP_USD=0.00
P68_KEYFRAME_EXECUTION_MODE=local_preview
P68_KEYFRAME_WIDTH=704
P68_KEYFRAME_HEIGHT=1280
"@
$envContent | Set-Content -Path $envPath -Encoding ASCII

Push-Location $deployRoot
try {
    if (-not $SkipImageBuild) {
        Write-Host "Building the pinned ComfyUI $comfyUiRef preview image. The first build can take several minutes..." -ForegroundColor Cyan
        & docker compose --env-file $envPath -f compose.yaml build
        if ($LASTEXITCODE -ne 0) {
            throw "Docker image build failed."
        }
    }

    & docker compose --env-file $envPath -f compose.yaml up -d
    if ($LASTEXITCODE -ne 0) {
        throw "The local keyframe worker did not start."
    }
}
finally {
    Pop-Location
}

Write-Host "Waiting for the local ComfyUI health endpoint..." -ForegroundColor Cyan
$deadline = (Get-Date).AddMinutes(10)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 5
        if ($response) {
            $healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 10
    }
}

if (-not $healthy) {
    Push-Location $deployRoot
    try {
        & docker compose --env-file $envPath -f compose.yaml logs --tail 120
    }
    finally {
        Pop-Location
    }
    throw "The worker did not become healthy within ten minutes."
}

Write-Host "LOCAL KEYFRAME WORKER READY" -ForegroundColor Green
Write-Host "ComfyUI: $comfyUiRef" -ForegroundColor Green
Write-Host "Endpoint: http://127.0.0.1:8188" -ForegroundColor Green
Write-Host "Preview canvas: 704x1280" -ForegroundColor Green
Write-Host "Local configuration: $envPath"
Write-Host "No generation, approval, upload, or publication was performed."
