[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$ModelKey,
  [Parameter(Mandatory=$true)]
  [string]$ModelDisplayName,
  [Parameter(Mandatory=$true)]
  [decimal]$PricePerSecondUsd,
  [Parameter(Mandatory=$true)]
  [string]$UsageTermsUrl,
  [Parameter(Mandatory=$true)]
  [string]$UsageEvidenceFile,
  [decimal]$MinDurationSeconds = 1,
  [decimal]$MaxDurationSeconds = 10,
  [decimal]$DurationStepSeconds = 1,
  [int]$Width = 720,
  [int]$Height = 1280,
  [int]$ExpectedLatencySeconds = 300,
  [decimal]$QualityRating = 80,
  [switch]$InstallSkills
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$EnvPath = Join-Path $Root ".env.local"
$KeyPath = Join-Path $Runtime "operator-keys.json"
$StatusPath = Join-Path $Runtime "higgsfield-readiness.json"
$RemoteDeploy = Join-Path $PSScriptRoot "deploy_remote_content_automation.ps1"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

if ($PricePerSecondUsd -le 0) { throw "PricePerSecondUsd must be greater than zero." }
if (-not (Test-Path -LiteralPath $UsageEvidenceFile)) {
  throw "Reviewed Higgsfield usage-terms evidence was not found: $UsageEvidenceFile"
}
if (-not (Test-Path -LiteralPath $EnvPath)) {
  throw "The Content Automation workstation is not installed. Run deploy_remote_content_automation.ps1 first."
}
if (-not (Test-Path -LiteralPath $KeyPath)) {
  throw "Operator keys are unavailable. Redeploy the simplified-role runtime first."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "Node.js/npm is required for the official Higgsfield CLI. Install Node.js LTS and rerun."
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

if (-not (Get-Command higgsfield -ErrorAction SilentlyContinue)) {
  Write-Host "Installing the official Higgsfield CLI..." -ForegroundColor Cyan
  & npm install --global @higgsfield/cli
  if ($LASTEXITCODE -ne 0) { throw "The official Higgsfield CLI installation failed." }
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machine;$user"
}
if (-not (Get-Command higgsfield -ErrorAction SilentlyContinue)) {
  throw "Higgsfield CLI installed but is not visible in this shell. Open a new PowerShell window and rerun."
}

Write-Host "A browser sign-in will open. Authenticate with the approved Content Automation Higgsfield account." -ForegroundColor Yellow
& higgsfield auth login
if ($LASTEXITCODE -ne 0) { throw "Higgsfield account authentication did not complete successfully." }

$modelJson = & higgsfield model get $ModelKey --json --no-color
if ($LASTEXITCODE -ne 0 -or -not $modelJson) {
  throw "The approved Higgsfield model is not available through the official account."
}
try { $modelEvidence = $modelJson | ConvertFrom-Json } catch { throw "Higgsfield model get did not return valid JSON." }

if ($InstallSkills) {
  & npx skills add higgsfield-ai/skills
  if ($LASTEXITCODE -ne 0) { throw "Higgsfield companion skill installation failed." }
}

$values = Read-DotEnv $EnvPath
$values["HIGGSFIELD_ENABLED"] = "true"
$values["HIGGSFIELD_CLI_PATH"] = (Get-Command higgsfield).Source
$values["HIGGSFIELD_WORKER_OPERATOR_ID"] = "higgsfield-worker"
$values["HIGGSFIELD_WORKER_LEASE_SECONDS"] = "1800"
$values["HIGGSFIELD_POLL_SECONDS"] = "5"
Write-DotEnv $values $EnvPath

& powershell -NoProfile -ExecutionPolicy Bypass -File $RemoteDeploy `
  -SkipComfyUI `
  -SkipInstall `
  -SkipModelPull
if ($LASTEXITCODE -ne 0) { throw "Runtime restart after Higgsfield enablement failed." }

$keys = Get-Content -LiteralPath $KeyPath -Raw | ConvertFrom-Json
$adminKey = [string]$keys.'local-super-admin'
if (-not $adminKey) { $adminKey = [string]$keys.'local-admin' }
if (-not $adminKey) { throw "No Super Admin or Admin key is available for renderer setup." }
$headers = @{ "X-Operator-Key" = $adminKey; "Content-Type" = "application/json" }
$api = "http://127.0.0.1:8000"
$termsDigest = (Get-FileHash -Algorithm SHA256 -LiteralPath $UsageEvidenceFile).Hash.ToLowerInvariant()
$recordedAt = (Get-Item -LiteralPath $UsageEvidenceFile).LastWriteTimeUtc.ToString("o")

$catalogue = Invoke-RestMethod -Uri "$api/renderers/catalogue?provider_key=higgsfield" -Headers $headers -TimeoutSec 20
$entry = @($catalogue.entries | Where-Object { $_.model_key -eq $ModelKey -and $_.status -ne "retired" }) | Select-Object -First 1
if (-not $entry) {
  $request = [ordered]@{
    provider_key = "higgsfield"
    provider_display_name = "Higgsfield"
    model_key = $ModelKey
    model_display_name = $ModelDisplayName
    operation = "image_to_video"
    adapter_kind = "managed_sdk"
    supported_formats = @("mp4")
    min_duration_seconds = [string]$MinDurationSeconds
    max_duration_seconds = [string]$MaxDurationSeconds
    duration_step_seconds = [string]$DurationStepSeconds
    supported_resolutions = @(@{ width = $Width; height = $Height })
    capabilities = @{
      image_conditioning = $true
      asynchronous_generation = $true
      official_cli = $true
      json_output = $true
      human_review_required = $true
    }
    expected_latency_seconds = @{ typical = $ExpectedLatencySeconds; maximum = ($ExpectedLatencySeconds * 3) }
    pricing = @{ per_second = [string]$PricePerSecondUsd }
    pricing_currency = "USD"
    quality_rating = [string]$QualityRating
    commercial_use_allowed = $true
    usage_terms_url = $UsageTermsUrl
    usage_evidence_digest = $termsDigest
    usage_evidence_recorded_at = $recordedAt
    data_handling = @{
      credentials = "official-cli-account-store"
      provider_history_is_not_canonical_storage = $true
      outputs_ingested_to_shared_artifact_store = $true
    }
    notes = "Official Higgsfield CLI adapter. Spend remains blocked until explicit P94 approval."
  }
  $created = Invoke-RestMethod -Method Post -Uri "$api/renderers/catalogue" -Headers $headers `
    -Body ($request | ConvertTo-Json -Depth 10) -TimeoutSec 30
  $entry = $created.entry
}
if ($entry.status -ne "active") {
  $activated = Invoke-RestMethod -Method Post -Uri "$api/renderers/catalogue/$($entry.id)/activate" `
    -Headers $headers -TimeoutSec 30
  $entry = $activated.entry
}

$health = [ordered]@{
  status = "healthy"
  checked_by = "setup-higgsfield-official"
  details = @{
    official_cli = $true
    account_authenticated = $true
    model_key = $ModelKey
    model_evidence = $modelEvidence
  }
}
Invoke-RestMethod -Method Post -Uri "$api/renderers/catalogue/$($entry.id)/health" -Headers $headers `
  -Body ($health | ConvertTo-Json -Depth 20) -TimeoutSec 30 | Out-Null

$status = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  official_cli_installed = $true
  interactive_auth_completed = $true
  credential_stored_outside_git = $true
  mcp_endpoint = "https://mcp.higgsfield.ai/mcp"
  renderer_entry_id = [string]$entry.id
  provider = "higgsfield"
  model_key = $ModelKey
  model_display_name = $ModelDisplayName
  worker_enabled = $true
  external_spend_enabled = $false
  external_fee_possible = $true
  automatic_spend_approval = $false
  real_generation_validated = $false
  usage_evidence_digest = $termsDigest
  next_gate = "Create an approved managed route, review the quote, and explicitly approve one shot before generation."
}
$status | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StatusPath -Encoding utf8

Write-Host "Official Higgsfield renderer and supervised worker are configured." -ForegroundColor Green
Write-Host "Renderer: $($entry.model_display_name) ($($entry.status))"
Write-Host "Readiness record: $StatusPath"
Write-Host "No generation or credit spend was triggered." -ForegroundColor Yellow
