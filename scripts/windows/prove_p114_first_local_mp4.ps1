[CmdletBinding()]
param(
    [string]$ComfyUIRoot = "D:\ComfyUI\App",
    [string]$TaskName = "ContentAutomationLocal",
    [switch]$ProbePrompt,
    [string]$DiagnosticInputImage = "",
    [int]$MinimumVramMiB = 20000
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$ManifestPath = Join-Path $Root "config\local-video-workflows\wan22-ti2v-5b.manifest.json"
$Collector = Join-Path $PSScriptRoot "collect_p114_workstation_evidence.ps1"
$Activation = Join-Path $PSScriptRoot "activate_p114_wan22.ps1"
$EvidenceRoot = Join-Path $Root ".runtime\p114-first-local-mp4"
$ComfyBaseUrl = "http://127.0.0.1:8188"
$ComfyPython = Join-Path $ComfyUIRoot ".venv\Scripts\python.exe"
$ComfyMain = Join-Path $ComfyUIRoot "main.py"
$TemporaryComfy = $null

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null

function Test-ComfyUIReady {
    try {
        $null = Invoke-RestMethod -Uri "$ComfyBaseUrl/system_stats" -TimeoutSec 5
        return $true
    } catch {
        return $false
    }
}

function Start-TemporaryComfyUI {
    if (Test-ComfyUIReady) { return $null }
    if (-not (Test-Path -LiteralPath $ComfyPython -PathType Leaf) -or
        -not (Test-Path -LiteralPath $ComfyMain -PathType Leaf)) {
        throw "ComfyUI is unavailable at $ComfyUIRoot"
    }
    $stdout = Join-Path $EvidenceRoot "temporary-comfyui.stdout.log"
    $stderr = Join-Path $EvidenceRoot "temporary-comfyui.stderr.log"
    $process = Start-Process -FilePath $ComfyPython `
        -ArgumentList @("main.py", "--listen", "127.0.0.1", "--port", "8188", "--disable-auto-launch") `
        -WorkingDirectory $ComfyUIRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -WindowStyle Minimized -PassThru
    $deadline = (Get-Date).AddMinutes(10)
    do {
        if ($process.HasExited) {
            if (Test-Path -LiteralPath $stderr) { Get-Content $stderr -Tail 200 }
            throw "Temporary ComfyUI exited before readiness."
        }
        Start-Sleep -Seconds 3
    } until ((Test-ComfyUIReady) -or (Get-Date) -gt $deadline)
    if (-not (Test-ComfyUIReady)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "ComfyUI did not become ready within ten minutes."
    }
    return $process
}

function Stop-TemporaryComfyUI([object]$Process) {
    if ($null -ne $Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        try { Wait-Process -Id $Process.Id -Timeout 30 -ErrorAction SilentlyContinue } catch {}
    }
}

function Invoke-JsonPython([string[]]$Arguments, [string]$OutputPath) {
    $stdout = Join-Path $EvidenceRoot ((Split-Path $OutputPath -Leaf) + ".stdout.log")
    $stderr = Join-Path $EvidenceRoot ((Split-Path $OutputPath -Leaf) + ".stderr.log")
    $process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr -Wait -PassThru -NoNewWindow
    $line = Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue |
        Where-Object { $_.Trim() } | Select-Object -Last 1
    if ($line) { $line | Set-Content -LiteralPath $OutputPath -Encoding UTF8 }
    if ($process.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $stderr) { Get-Content $stderr -Tail 200 }
        if ($line) { Write-Host $line -ForegroundColor Red }
        throw "Python proof step failed. Evidence: $EvidenceRoot"
    }
    if (-not $line) { throw "Python proof step returned no JSON." }
    return ($line | ConvertFrom-Json)
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Missing repository Python: $Python" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "Missing manifest: $ManifestPath" }
if (-not (Test-Path -LiteralPath $Collector -PathType Leaf)) { throw "Missing workstation collector." }
if (-not (Test-Path -LiteralPath $Activation -PathType Leaf)) { throw "Missing P114 activation script." }
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { throw "nvidia-smi is required." }

$gpuRows = @(& nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits)
if ($LASTEXITCODE -ne 0 -or -not $gpuRows) { throw "Unable to query NVIDIA GPU." }
$gpus = @()
foreach ($row in $gpuRows) {
    $parts = $row -split ",\s*"
    if ($parts.Count -ge 3) {
        $gpus += [ordered]@{ name = $parts[0]; memory_total_mib = [int]$parts[1]; driver = $parts[2] }
    }
}
$selectedGpu = $gpus | Sort-Object memory_total_mib -Descending | Select-Object -First 1
if ($null -eq $selectedGpu -or $selectedGpu.memory_total_mib -lt $MinimumVramMiB) {
    throw "At least $MinimumVramMiB MiB VRAM is required for this 24 GB-class proof."
}
$gpus | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $EvidenceRoot "gpu-hardware.json") -Encoding UTF8

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$workflowPath = Join-Path $Root ([string]$manifest.workflow_path)
$modelRoot = Join-Path $ComfyUIRoot "models"
$modelPaths = @($manifest.model_files | ForEach-Object { Join-Path $modelRoot ([string]$_.path) })

try {
    $TemporaryComfy = Start-TemporaryComfyUI

    & $Collector -ComfyUIRoot $ComfyUIRoot -WorkflowPath $workflowPath -ModelPaths $modelPaths `
        -ComfyUIBaseUrl $ComfyBaseUrl -OutputPath (Join-Path $EvidenceRoot "workstation-evidence.json")
    if ($LASTEXITCODE -ne 0) { throw "Workstation evidence collection failed." }

    $diagnosticArgs = @(
        "-m", "src.operations.p114_comfyui_diagnostics",
        "--base-url", $ComfyBaseUrl,
        "--manifest", $ManifestPath,
        "--output", (Join-Path $EvidenceRoot "comfyui-diagnostic.json")
    )
    if ($ProbePrompt) {
        $inputPath = $DiagnosticInputImage
        if (-not $inputPath) {
            $keyframe = Invoke-JsonPython @("-m", "src.operations.p114_latest_keyframe") `
                (Join-Path $EvidenceRoot "approved-keyframe.json")
            $inputPath = [string]$keyframe.path
        }
        if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) {
            throw "Diagnostic input image is unavailable: $inputPath"
        }
        $diagnosticArgs += @("--input-image", (Resolve-Path $inputPath).Path, "--submit-prompt")
    }
    $null = Invoke-JsonPython $diagnosticArgs (Join-Path $EvidenceRoot "comfyui-diagnostic.json")

    Stop-TemporaryComfyUI $TemporaryComfy
    $TemporaryComfy = $null

    & $Activation -ComfyUIRoot $ComfyUIRoot -TaskName $TaskName
    if ($LASTEXITCODE -ne 0) {
        throw "P114 activation/proof failed. The canonical worker log preserves the complete ComfyUI HTTP rejection body."
    }

    $proof = Invoke-JsonPython @("-m", "src.operations.p114_first_mp4_evidence") `
        (Join-Path $EvidenceRoot "first-local-mp4-evidence.json")

    [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        ok = $true
        generation_job_id = $proof.generation_job_id
        generation_attempt_id = $proof.generation_attempt_id
        output_asset_id = $proof.output_asset_id
        external_cost_usd = $proof.external_cost_usd
        evidence_root = $EvidenceRoot
        human_review_still_required = $true
        automatic_paid_generation = $false
        automatic_approval = $false
        automatic_public_publishing = $false
    } | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $EvidenceRoot "summary.json") -Encoding UTF8

    Write-Host "P114 FIRST LOCAL MP4 PROOF PASSED" -ForegroundColor Green
    Write-Host "Evidence: $EvidenceRoot"
    Write-Host "The MP4 remains internal-only and pending explicit human review." -ForegroundColor Yellow
} catch {
    Stop-TemporaryComfyUI $TemporaryComfy
    [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        ok = $false
        error = "{0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message
        evidence_root = $EvidenceRoot
        automatic_paid_generation = $false
        automatic_approval = $false
        automatic_public_publishing = $false
    } | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $EvidenceRoot "summary.json") -Encoding UTF8
    throw
}
