param(
    [string]$DataRoot = "D:\content-automation-data\p68-keyframe-worker",
    [string]$Pilot = "animal-octopus-arms",
    [string]$Shot = "S01",
    [int]$TimeoutMinutes = 60
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$envPath = Join-Path $DataRoot "local-keyframe-worker.env"
$licenseEvidence = Join-Path $DataRoot "sdxl-base-license-evidence.json"
$artifactRoot = Join-Path $DataRoot "artifacts"
$cli = Join-Path $repoRoot "scripts\p68_generate_keyframes.py"

if (-not (Test-Path $envPath)) {
    throw "Local worker configuration is missing. Run setup_p68_local_keyframe_worker.ps1 first."
}
if (-not (Test-Path $licenseEvidence)) {
    throw "Local model licence evidence is missing. Run the guarded setup with -AcceptModelLicense first."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is required and was not found."
}

Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) {
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
}

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 10 | Out-Null
}
catch {
    throw "The local keyframe worker is not healthy at http://127.0.0.1:8188. Run the setup script first."
}

& python -c "import httpx; from PIL import Image" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing focused local client dependencies..." -ForegroundColor Cyan
    & python -m pip install --disable-pip-version-check httpx pillow
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install the focused Python client dependencies."
    }
}

New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
Set-Location $repoRoot

Write-Host "Planning one local preview keyframe: $Pilot/$Shot at 704x1280" -ForegroundColor Cyan
$planText = & python $cli plan `
    --pilot $Pilot `
    --shots $Shot `
    --artifact-root $artifactRoot `
    --width 704 `
    --height 1280 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Keyframe plan failed:`n$($planText -join [Environment]::NewLine)"
}
$plan = ($planText -join [Environment]::NewLine) | ConvertFrom-Json
if ($plan.request_count -ne 1) {
    throw "Expected exactly one eligible keyframe request, found $($plan.request_count)."
}

Write-Host "Submitting one zero-cost local preview job..." -ForegroundColor Cyan
$submitText = & python $cli submit `
    --pilot $Pilot `
    --shots $Shot `
    --limit 1 `
    --runtime-seconds 600 `
    --artifact-root $artifactRoot `
    --width 704 `
    --height 1280 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Keyframe submission failed:`n$($submitText -join [Environment]::NewLine)"
}
$submit = ($submitText -join [Environment]::NewLine) | ConvertFrom-Json
if (($submit.submitted | Measure-Object).Count -eq 0 -and ($submit.cached | Measure-Object).Count -eq 0) {
    throw "No local preview job was submitted or found in cache: $($submitText -join [Environment]::NewLine)"
}

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 20
    $refreshText = & python $cli refresh `
        --pilot $Pilot `
        --shots $Shot `
        --artifact-root $artifactRoot `
        --width 704 `
        --height 1280 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Keyframe refresh failed:`n$($refreshText -join [Environment]::NewLine)"
    }
    $refresh = ($refreshText -join [Environment]::NewLine) | ConvertFrom-Json

    if (($refresh.failed | Measure-Object).Count -gt 0) {
        throw "Local preview generation failed: $($refresh.failed | ConvertTo-Json -Depth 6)"
    }
    if (($refresh.completed | Measure-Object).Count -gt 0) {
        $provenancePath = Join-Path $artifactRoot "gold\$Pilot\generated-assets\keyframe-provenance.json"
        if (-not (Test-Path $provenancePath)) {
            throw "Generation completed but provenance was not written."
        }
        $provenance = Get-Content $provenancePath -Raw | ConvertFrom-Json
        $record = $provenance.shots.$Shot
        if (-not $record) {
            throw "Generation completed but no provenance record exists for $Pilot/$Shot."
        }
        if ($record.human_review_status -ne "pending_keyframe_review") {
            throw "Unsafe local sample status: expected pending_keyframe_review, found $($record.human_review_status)."
        }
        if ($record.approved_for_generation -eq $true -or $record.publish_allowed -eq $true) {
            throw "Unsafe local sample state: automatic approval or publication was detected."
        }
        Write-Host "LOCAL KEYFRAME SAMPLE READY FOR HUMAN REVIEW" -ForegroundColor Green
        Write-Host "Pilot/shot: $Pilot/$Shot"
        Write-Host "Image: $($record.normalized_path)" -ForegroundColor Green
        Write-Host "Status: pending_keyframe_review"
        Write-Host "Approved for video generation: false"
        Write-Host "Publish allowed: false"
        exit 0
    }

    $pendingCount = ($refresh.pending | Measure-Object).Count
    Write-Host "Still processing locally; pending jobs: $pendingCount" -ForegroundColor DarkCyan
}

throw "The local preview job did not finish within $TimeoutMinutes minutes. It remains unapproved and unpublished."
