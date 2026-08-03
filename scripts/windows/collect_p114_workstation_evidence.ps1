param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [Parameter(Mandatory = $true)]
    [string]$WorkflowPath,

    [Parameter(Mandatory = $true)]
    [string[]]$ModelPaths,

    [string]$ComfyUIBaseUrl = "http://127.0.0.1:8188",

    [string]$OutputPath = ".runtime\p114-workstation-evidence.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-RequiredFileEvidence {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction Stop
    $item = Get-Item -LiteralPath $resolved.Path -ErrorAction Stop
    if ($item.PSIsContainer) {
        throw "Expected a file but received a directory: $Path"
    }

    $hash = Get-FileHash -LiteralPath $resolved.Path -Algorithm SHA256
    return [ordered]@{
        path = $resolved.Path
        name = $item.Name
        size_bytes = [int64]$item.Length
        sha256 = $hash.Hash.ToLowerInvariant()
        last_write_time_utc = $item.LastWriteTimeUtc.ToString("o")
    }
}

function Get-GitRepositoryEvidence {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath (Join-Path $Path ".git"))) {
        return [ordered]@{
            path = $Path
            is_git_repository = $false
            commit = $null
            branch = $null
            dirty = $null
            remote = $null
        }
    }

    $commit = (& git -C $Path rev-parse HEAD 2>$null).Trim()
    $branch = (& git -C $Path branch --show-current 2>$null).Trim()
    $status = @(& git -C $Path status --porcelain 2>$null)
    $remote = (& git -C $Path remote get-url origin 2>$null).Trim()

    return [ordered]@{
        path = (Resolve-Path -LiteralPath $Path).Path
        is_git_repository = $true
        commit = $commit
        branch = $branch
        dirty = ($status.Count -gt 0)
        remote = $remote
    }
}

function Get-CommandEvidence {
    param([Parameter(Mandatory = $true)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return $null
    }

    return [ordered]@{
        name = $Name
        source = $command.Source
        version = if ($command.Version) { $command.Version.ToString() } else { $null }
    }
}

$uri = [System.Uri]$ComfyUIBaseUrl
if ($uri.Scheme -notin @("http", "https")) {
    throw "ComfyUIBaseUrl must use http or https."
}
if ($uri.Host -notin @("127.0.0.1", "localhost", "::1")) {
    throw "ComfyUI must remain loopback-only for P114 activation. Received host: $($uri.Host)"
}

$resolvedRoot = Resolve-Path -LiteralPath $ComfyUIRoot -ErrorAction Stop
$workflow = Get-RequiredFileEvidence -Path $WorkflowPath
$models = @($ModelPaths | ForEach-Object { Get-RequiredFileEvidence -Path $_ })

$customNodesRoot = Join-Path $resolvedRoot.Path "custom_nodes"
$customNodes = @()
if (Test-Path -LiteralPath $customNodesRoot) {
    $customNodes = @(
        Get-ChildItem -LiteralPath $customNodesRoot -Directory |
            Sort-Object Name |
            ForEach-Object { Get-GitRepositoryEvidence -Path $_.FullName }
    )
}

$gpu = $null
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($null -ne $nvidiaSmi) {
    $gpuRows = @(
        & nvidia-smi --query-gpu=name,driver_version,memory.total,temperature.gpu,power.limit --format=csv,noheader,nounits 2>$null
    )
    $gpu = @(
        foreach ($row in $gpuRows) {
            $parts = $row -split ",\s*"
            [ordered]@{
                name = $parts[0]
                driver_version = $parts[1]
                memory_total_mb = [int]$parts[2]
                temperature_c = [int]$parts[3]
                power_limit_w = [double]$parts[4]
            }
        }
    )
}

$comfyHealth = [ordered]@{
    base_url = $ComfyUIBaseUrl
    loopback_only = $true
    reachable = $false
    status_code = $null
    checked_at_utc = (Get-Date).ToUniversalTime().ToString("o")
}
try {
    $response = Invoke-WebRequest -Uri "$ComfyUIBaseUrl/system_stats" -UseBasicParsing -TimeoutSec 10
    $comfyHealth.reachable = $true
    $comfyHealth.status_code = [int]$response.StatusCode
} catch {
    $comfyHealth.error = $_.Exception.Message
}

$evidence = [ordered]@{
    schema = "p114-workstation-evidence/v1"
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    machine = [ordered]@{
        computer_name = $env:COMPUTERNAME
        os = [System.Environment]::OSVersion.VersionString
        powershell = $PSVersionTable.PSVersion.ToString()
        python = Get-CommandEvidence -Name "python"
        ffmpeg = Get-CommandEvidence -Name "ffmpeg"
        git = Get-CommandEvidence -Name "git"
        gpu = $gpu
    }
    comfyui = [ordered]@{
        repository = Get-GitRepositoryEvidence -Path $resolvedRoot.Path
        health = $comfyHealth
        custom_nodes = $customNodes
    }
    workflow = $workflow
    models = $models
    activation = [ordered]@{
        renderer = "wan2.2-ti2v-5b"
        external_fee_usd = 0
        automatic_paid_generation = $false
        automatic_public_publishing = $false
        ready_for_activation = (
            $comfyHealth.reachable -and
            -not $evidence.comfyui.repository.dirty -and
            ($models.Count -gt 0)
        )
    }
}

# Recompute without self-reference for compatibility with strict PowerShell modes.
$evidence.activation.ready_for_activation = (
    $comfyHealth.reachable -and
    -not [bool]$evidence.comfyui.repository.dirty -and
    ($models.Count -gt 0)
)

$outputParent = Split-Path -Parent $OutputPath
if ($outputParent) {
    New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
}

$evidence | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "P114 workstation evidence written to $OutputPath"
Write-Host "Workflow SHA-256: $($workflow.sha256)"
Write-Host "Model files: $($models.Count)"
Write-Host "Custom-node repositories: $($customNodes.Count)"
Write-Host "ComfyUI reachable: $($comfyHealth.reachable)"
Write-Host "Ready for controlled activation: $($evidence.activation.ready_for_activation)"

if (-not $evidence.activation.ready_for_activation) {
    exit 2
}
