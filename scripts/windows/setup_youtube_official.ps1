[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$GoogleOAuthClientJson,
  [Parameter(Mandatory=$true)]
  [string]$ChannelReference,
  [string]$TargetKey = "youtube-official-main",
  [string]$DisplayName = "Official YouTube Channel",
  [string]$TimeZone = "Asia/Karachi",
  [switch]$AllowUnlisted,
  [switch]$AllowPublic,
  [switch]$NotifySubscribers
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$EnvPath = Join-Path $Root ".env.local"
$KeyPath = Join-Path $Runtime "operator-keys.json"
$CredentialPath = Join-Path $Runtime "youtube-oauth.json"
$OAuthScript = Join-Path $Root "scripts\setup_youtube_oauth.py"
$RemoteDeploy = Join-Path $PSScriptRoot "deploy_remote_content_automation.ps1"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

if (-not (Test-Path -LiteralPath $GoogleOAuthClientJson)) {
  throw "Google OAuth client JSON was not found: $GoogleOAuthClientJson"
}
if (-not (Test-Path -LiteralPath $EnvPath)) {
  throw "The local runtime is not installed. Run deploy_remote_content_automation.ps1 first."
}
if (-not (Test-Path -LiteralPath $KeyPath)) {
  throw "Operator keys are unavailable. Redeploy the simplified-role runtime first."
}
if (-not (Test-Path -LiteralPath $Python)) {
  $Python = (Get-Command python -ErrorAction Stop).Source
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

Write-Host "Starting official Google OAuth authorization for YouTube..." -ForegroundColor Cyan
& $Python $OAuthScript `
  --client-json (Resolve-Path $GoogleOAuthClientJson) `
  --output $CredentialPath
if ($LASTEXITCODE -ne 0) { throw "YouTube OAuth authorization failed." }

# Restrict the refresh-token file to the current Windows user.
& icacls.exe $CredentialPath /inheritance:r 1>$null
& icacls.exe $CredentialPath /grant:r "${env:USERNAME}:(R,W)" 1>$null
if ($LASTEXITCODE -ne 0) { throw "Could not restrict the YouTube OAuth credential file." }

$values = Read-DotEnv $EnvPath
$values["YOUTUBE_CREDENTIAL_FILE"] = $CredentialPath
Write-DotEnv $values $EnvPath

# Restart the managed runtime so the official adapter inherits the credential reference.
& powershell -NoProfile -ExecutionPolicy Bypass -File $RemoteDeploy `
  -SkipComfyUI `
  -SkipInstall `
  -SkipModelPull
if ($LASTEXITCODE -ne 0) { throw "Runtime restart after YouTube authorization failed." }

$keys = Get-Content -LiteralPath $KeyPath -Raw | ConvertFrom-Json
$adminKey = [string]$keys.'local-super-admin'
if (-not $adminKey) { $adminKey = [string]$keys.'local-admin' }
if (-not $adminKey) { throw "No Super Admin or Admin key is available for target setup." }
$headers = @{ "X-Operator-Key" = $adminKey; "Content-Type" = "application/json" }
$api = "http://127.0.0.1:8000"

$existing = Invoke-RestMethod -Uri "$api/delivery-targets?include_retired=true" -Headers $headers -TimeoutSec 15
$target = @($existing.items | Where-Object { $_.target_key -eq $TargetKey -and $_.status -ne "retired" }) | Select-Object -First 1

if (-not $target) {
  $privacy = @("private")
  if ($AllowUnlisted) { $privacy += "unlisted" }
  if ($AllowPublic) { $privacy += "public" }
  $request = [ordered]@{
    target_key = $TargetKey
    display_name = $DisplayName
    platform = "youtube"
    environment = "staging"
    target_account_ref = $ChannelReference
    time_zone = $TimeZone
    primary_adapter_key = "youtube-official"
    fallback_adapter_key = $null
    supported_privacy = $privacy
    default_privacy = "private"
    credential_secret_ref = "env:YOUTUBE_CREDENTIAL_FILE"
    simulated = $false
    execution_enabled = $true
    requests_per_minute = 6
    requests_per_day = 50
    title_max_length = 100
    caption_max_length = 5000
    hashtag_limit = 15
    thumbnail_required = $false
    disclosure_required = $true
    configuration = [ordered]@{
      allow_unlisted = [bool]$AllowUnlisted
      allow_public = [bool]$AllowPublic
      notify_subscribers = [bool]$NotifySubscribers
      contains_synthetic_media = $true
      made_for_kids = $false
      embeddable = $true
      category_id = "22"
      default_language = "en"
    }
  }
  $created = Invoke-RestMethod -Method Post -Uri "$api/delivery-targets" -Headers $headers `
    -Body ($request | ConvertTo-Json -Depth 10) -TimeoutSec 30
  $target = $created.target
}

if ($target.status -ne "active") {
  $activated = Invoke-RestMethod -Method Post -Uri "$api/delivery-targets/$($target.id)/activate" `
    -Headers $headers -TimeoutSec 30
  $target = $activated.target
}

$status = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  target_id = [string]$target.id
  target_key = [string]$target.target_key
  channel_reference = $ChannelReference
  status = [string]$target.status
  adapter = "youtube-official"
  default_privacy = "private"
  allow_unlisted = [bool]$AllowUnlisted
  allow_public = [bool]$AllowPublic
  notify_subscribers = [bool]$NotifySubscribers
  credential_reference = "env:YOUTUBE_CREDENTIAL_FILE"
  credential_file = $CredentialPath
  upload_executed = $false
  next_step = "Create an approved release and run one private delivery through Creator Studio."
}
$statusPath = Join-Path $Runtime "youtube-readiness.json"
$status | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $statusPath -Encoding utf8

Write-Host "Official YouTube account and private delivery target are configured." -ForegroundColor Green
Write-Host "Target: $($target.target_key) ($($target.status))"
Write-Host "Readiness: $statusPath"
Write-Host "No video was uploaded. The first delivery remains a separate human-approved private test." -ForegroundColor Yellow
