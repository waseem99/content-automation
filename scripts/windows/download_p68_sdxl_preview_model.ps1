param(
    [string]$DataRoot = "D:\content-automation-data\p68-keyframe-worker",
    [switch]$AcceptModelLicense
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $AcceptModelLicense) {
    throw "Model download is blocked until -AcceptModelLicense is supplied after reviewing the CreativeML Open RAIL++-M licence."
}

$modelName = "sd_xl_base_1.0.safetensors"
$modelRevision = "a7c2bcc30a3b5489f1f1989e66cd5fe957fdb45c"
$expectedSha256 = "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b"
$licenseUrl = "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md"
$downloadUrl = "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/${modelRevision}/${modelName}?download=true"
$modelDir = Join-Path $DataRoot "models"
$modelPath = Join-Path $modelDir $modelName
$partialPath = "$modelPath.partial"
$evidencePath = Join-Path $DataRoot "sdxl-base-license-evidence.json"

New-Item -ItemType Directory -Force -Path $modelDir | Out-Null

$drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($DataRoot).TrimEnd(':','\')) -ErrorAction Stop
if ($drive.Free -lt 12GB) {
    throw "At least 12 GB free disk space is required on the selected drive."
}

if (Test-Path $modelPath) {
    $existingHash = (Get-FileHash -Path $modelPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($existingHash -eq $expectedSha256) {
        Write-Host "Verified SDXL preview checkpoint already exists." -ForegroundColor Green
    }
    else {
        throw "An existing checkpoint has the wrong SHA256. Move or delete it before retrying: $modelPath"
    }
}
else {
    Write-Host "Downloading the official SDXL Base 1.0 checkpoint (approximately 6.94 GB)..." -ForegroundColor Cyan
    & curl.exe -L --fail --retry 5 --retry-delay 5 -C - --output $partialPath $downloadUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Checkpoint download failed. The partial file is preserved for resume: $partialPath"
    }

    $downloadedHash = (Get-FileHash -Path $partialPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($downloadedHash -ne $expectedSha256) {
        throw "Downloaded checkpoint SHA256 did not match the reviewed manifest."
    }
    Move-Item -Force $partialPath $modelPath
}

$evidence = [ordered]@{
    schema_version = "p68.local_preview_model_evidence.v1"
    model_id = "stabilityai/stable-diffusion-xl-base-1.0"
    filename = $modelName
    source_revision = $modelRevision
    sha256 = $expectedSha256
    license_type = "CreativeML Open RAIL++-M"
    license_url = $licenseUrl
    license_accepted_locally = $true
    accepted_at_utc = [DateTime]::UtcNow.ToString("o")
    execution_scope = "local_preview_keyframes_only"
    quality_approved = $false
    publish_allowed = $false
}
$evidence | ConvertTo-Json -Depth 5 | Set-Content -Path $evidencePath -Encoding UTF8

Write-Host "Checkpoint verified: $modelPath" -ForegroundColor Green
Write-Host "Licence evidence written: $evidencePath" -ForegroundColor Green
