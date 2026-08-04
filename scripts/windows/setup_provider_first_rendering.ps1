[CmdletBinding()]
param(
  [ValidateSet("fal", "vidu", "both")]
  [string]$Provider = "both",

  [string]$FalModelKey = "fal-ai/wan/v2.2-5b/image-to-video",
  [string]$FalModelDisplayName = "Wan 2.2 5B Image to Video on fal",
  [decimal]$FalPricePerRequestUsd = 0,
  [string]$FalUsageTermsUrl = "",
  [string]$FalUsageEvidenceFile = "",

  [string]$ViduModelKey = "viduq3-pro-fast",
  [string]$ViduModelDisplayName = "Vidu Q3 Pro Fast Image to Video",
  [decimal]$ViduPricePerSecondUsd = 0,
  [decimal]$ViduUsdPerCredit = 0,
  [string]$ViduUsageTermsUrl = "",
  [string]$ViduUsageEvidenceFile = "",

  [switch]$EnablePaidExecution,
  [switch]$InstallAlwaysOnWorkers
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$EnvPath = Join-Path $Root ".env.local"
$KeyPath = Join-Path $Runtime "operator-keys.json"
$StatusPath = Join-Path $Runtime "provider-first-readiness.json"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$InstallWorkers = Join-Path $PSScriptRoot "install_provider_workers_service.ps1"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

function Includes-Provider([string]$Name) {
  return $Provider -eq "both" -or $Provider -eq $Name
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
  [IO.File]::WriteAllLines(
    $Path,
    [string[]]@($Values.Keys | ForEach-Object { "$_=$($Values[$_])" }),
    (New-Object Text.UTF8Encoding($false))
  )
}

function Import-Environment([System.Collections.IDictionary]$Values) {
  foreach ($entry in $Values.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable([string]$entry.Key, [string]$entry.Value, "Process")
  }
}

function Ensure-Secret([string]$Name, [string]$Label) {
  $existing = [Environment]::GetEnvironmentVariable($Name, "User")
  if (-not [string]::IsNullOrWhiteSpace($existing)) {
    [Environment]::SetEnvironmentVariable($Name, $existing, "Process")
    return
  }
  $secure = Read-Host "$Label (input is hidden)" -AsSecureString
  $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if ([string]::IsNullOrWhiteSpace($plain)) { throw "$Label cannot be empty." }
    [Environment]::SetEnvironmentVariable($Name, $plain, "User")
    [Environment]::SetEnvironmentVariable($Name, $plain, "Process")
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
  }
}

function Assert-Evidence([string]$Name, [decimal]$Price, [string]$TermsUrl, [string]$EvidenceFile) {
  if ($Price -le 0) { throw "$Name price must be greater than zero and based on reviewed current pricing." }
  if ($TermsUrl -notmatch '^https://') { throw "$Name usage terms URL must use HTTPS." }
  if (-not (Test-Path -LiteralPath $EvidenceFile -PathType Leaf)) {
    throw "$Name reviewed usage evidence file was not found: $EvidenceFile"
  }
}

function Invoke-RendererSetup(
  [string]$ProviderKey,
  [string]$ProviderName,
  [string]$ModelKey,
  [string]$ModelName,
  [hashtable]$Pricing,
  [string]$TermsUrl,
  [string]$EvidenceFile,
  [decimal]$MaximumDuration,
  [array]$Resolutions,
  [hashtable]$Capabilities
) {
  $termsDigest = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidenceFile).Hash.ToLowerInvariant()
  $recordedAt = (Get-Item -LiteralPath $EvidenceFile).LastWriteTimeUtc.ToString("o")
  $catalogue = Invoke-RestMethod -Uri "$api/renderers/catalogue?provider_key=$ProviderKey" -Headers $headers -TimeoutSec 20
  $entry = @(
    $catalogue.entries |
      Where-Object { $_.model_key -eq $ModelKey -and $_.operation -eq "image_to_video" -and $_.status -ne "retired" }
  ) | Select-Object -First 1

  if (-not $entry) {
    $request = [ordered]@{
      provider_key = $ProviderKey
      provider_display_name = $ProviderName
      model_key = $ModelKey
      model_display_name = $ModelName
      operation = "image_to_video"
      adapter_kind = "http_api"
      supported_formats = @("mp4")
      min_duration_seconds = "1"
      max_duration_seconds = [string]$MaximumDuration
      duration_step_seconds = "1"
      supported_resolutions = $Resolutions
      capabilities = $Capabilities
      expected_latency_seconds = @{ p50 = 300; maximum = 1800; per_output_second = 30 }
      # Legacy generic shape retained only as a migration marker: pricing = @{ per_second_usd = [string]$PricePerSecond }
      pricing = $Pricing
      pricing_currency = "USD"
      quality_rating = "82"
      commercial_use_allowed = $true
      usage_terms_url = $TermsUrl
      usage_evidence_digest = $termsDigest
      usage_evidence_recorded_at = $recordedAt
      data_handling = @{
        credentials = "windows-user-environment"
        credentials_in_git = $false
        credentials_in_postgresql = $false
        provider_history_is_not_canonical_storage = $true
        outputs_downloaded_immediately = $true
        outputs_ingested_to_shared_artifact_store = $true
      }
      notes = "Official provider API adapter. Every request requires an approved route and spend reservation."
    }
    $created = Invoke-RestMethod -Method Post -Uri "$api/renderers/catalogue" -Headers $headers `
      -Body ($request | ConvertTo-Json -Depth 12) -TimeoutSec 30
    $entry = $created.entry
  }
  if ($entry.status -ne "active") {
    $entry = (Invoke-RestMethod -Method Post -Uri "$api/renderers/catalogue/$($entry.id)/activate" `
      -Headers $headers -TimeoutSec 30).entry
  }
  $health = [ordered]@{
    status = "degraded"
    checked_by = "setup-provider-first-rendering"
    details = @{
      official_api_configured = $true
      credentials_present = $true
      model_key = $ModelKey
      paid_generation_not_run_during_setup = $true
      first_live_request_requires_explicit_spend_approval = $true
    }
  }
  Invoke-RestMethod -Method Post -Uri "$api/renderers/catalogue/$($entry.id)/health" -Headers $headers `
    -Body ($health | ConvertTo-Json -Depth 10) -TimeoutSec 30 | Out-Null
  return $entry
}

if (-not (Test-Path -LiteralPath $EnvPath)) { throw ".env.local is missing." }
if (-not (Test-Path -LiteralPath $KeyPath)) { throw "Operator keys are missing." }
if (-not (Test-Path -LiteralPath $Python)) { throw "The Python environment is missing." }

if (Includes-Provider "fal") {
  Assert-Evidence "fal" $FalPricePerRequestUsd $FalUsageTermsUrl $FalUsageEvidenceFile
  Ensure-Secret "FAL_KEY" "fal API key"
}
if (Includes-Provider "vidu") {
  Assert-Evidence "Vidu" $ViduPricePerSecondUsd $ViduUsageTermsUrl $ViduUsageEvidenceFile
  Ensure-Secret "VIDU_API_KEY" "Vidu API key"
}

$values = Read-DotEnv $EnvPath
$values["PROVIDER_PAID_EXECUTION_ENABLED"] = if ($EnablePaidExecution) { "true" } else { "false" }
$values["HYBRID_PUBLIC_PUBLISHING_ENABLED"] = "false"
if (Includes-Provider "fal") {
  $values["FAL_RENDERER_ENABLED"] = "true"
  $values["FAL_QUEUE_BASE_URL"] = "https://queue.fal.run"
  $values["FAL_WORKER_OPERATOR_ID"] = "fal-worker"
  $values["FAL_WORKER_LEASE_SECONDS"] = "1800"
  $values["FAL_POLL_SECONDS"] = "5"
}
if (Includes-Provider "vidu") {
  $values["VIDU_RENDERER_ENABLED"] = "true"
  $values["VIDU_API_BASE_URL"] = "https://api.vidu.com"
  $values["VIDU_WORKER_OPERATOR_ID"] = "vidu-worker"
  $values["VIDU_WORKER_LEASE_SECONDS"] = "1800"
  $values["VIDU_POLL_SECONDS"] = "5"
  if ($ViduUsdPerCredit -gt 0) { $values["VIDU_USD_PER_CREDIT"] = [string]$ViduUsdPerCredit }
}
Write-DotEnv $values $EnvPath
Import-Environment $values

$ready = Invoke-RestMethod -Uri "http://127.0.0.1:8000/runtime/ready" -TimeoutSec 10
if (-not $ready.ok) { throw "Creator Studio is not ready." }

Push-Location $Root
try {
  & $Python -m src.operations.provider_worker_onboarding
  if ($LASTEXITCODE -ne 0) { throw "Provider worker onboarding failed." }
} finally {
  Pop-Location
}

$keys = Get-Content -LiteralPath $KeyPath -Raw | ConvertFrom-Json
$adminKey = [string]$keys.'local-super-admin'
if (-not $adminKey) { $adminKey = [string]$keys.'local-admin' }
if (-not $adminKey) { throw "No Super Admin or Admin key is available." }
$headers = @{ "X-Operator-Key" = $adminKey; "Content-Type" = "application/json" }
$api = "http://127.0.0.1:8000"
$entries = @()

if (Includes-Provider "fal") {
  $entries += Invoke-RendererSetup "fal" "fal" $FalModelKey $FalModelDisplayName `
    @{ per_request_usd = [string]$FalPricePerRequestUsd } `
    $FalUsageTermsUrl $FalUsageEvidenceFile 5 `
    @(@{ width = 1280; height = 720 }, @{ width = 720; height = 1280 }) `
    @{
      image_conditioning = $true
      asynchronous_generation = $true
      official_http_api = $true
      queue_polling = $true
      request_id_recovery = $true
      data_uri_input = $true
      human_review_required = $true
      global_public_candidate = $true
      fixed_request_billing = $true
    }
}
if (Includes-Provider "vidu") {
  $entries += Invoke-RendererSetup "vidu" "Vidu" $ViduModelKey $ViduModelDisplayName `
    @{ per_second_usd = [string]$ViduPricePerSecondUsd } `
    $ViduUsageTermsUrl $ViduUsageEvidenceFile 16 `
    @(
      @{ width = 1280; height = 720 }, @{ width = 720; height = 1280 },
      @{ width = 1920; height = 1080 }, @{ width = 1080; height = 1920 }
    ) `
    @{
      image_conditioning = $true
      asynchronous_generation = $true
      official_http_api = $true
      queue_polling = $true
      request_id_recovery = $true
      data_uri_input = $true
      start_frame = $true
      human_review_required = $true
    }
}

if ($InstallAlwaysOnWorkers) {
  if (-not $EnablePaidExecution) {
    throw "-InstallAlwaysOnWorkers requires -EnablePaidExecution."
  }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $InstallWorkers
  if ($LASTEXITCODE -ne 0) { throw "Provider worker scheduled-task installation failed." }
}

$status = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  provider_first_control_plane = $true
  providers = @($entries | ForEach-Object {
    @{ provider = $_.provider_key; model = $_.model_key; entry_id = [string]$_.id; status = $_.status; health = "degraded_pending_first_live_validation" }
  })
  credentials_stored_outside_git = $true
  credentials_stored_outside_postgresql = $true
  paid_execution_enabled = [bool]$EnablePaidExecution
  always_on_workers_installed = [bool]$InstallAlwaysOnWorkers
  automatic_spend_approval = $false
  automatic_creative_approval = $false
  automatic_publishing = $false
  real_generation_validated = $false
  next_gate = "Create an approved P94 managed route, approve its spend ceiling, run one internal clip, and complete human review."
}
$status | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $StatusPath -Encoding utf8

Write-Host "Provider-first rendering is configured." -ForegroundColor Green
Write-Host "Readiness record: $StatusPath"
Write-Host "No generation or credit spend was triggered during setup." -ForegroundColor Yellow
if (-not $EnablePaidExecution) {
  Write-Host "Workers remain disabled until the setup is rerun with -EnablePaidExecution." -ForegroundColor Yellow
}
