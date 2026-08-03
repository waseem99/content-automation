[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("fal", "vidu")]
  [string]$Provider,

  [Parameter(Mandatory=$true)]
  [string]$RoutingPlanId,

  [Parameter(Mandatory=$true)]
  [string]$ReservationPayloadFile,

  [Parameter(Mandatory=$true)]
  [decimal]$MaximumSpendUsd,

  [Parameter(Mandatory=$true)]
  [string]$Confirmation,

  [string]$BaseUrl = "http://127.0.0.1:8000",
  [switch]$Headed
)

$ErrorActionPreference = "Stop"
if ($MaximumSpendUsd -le 0 -or $MaximumSpendUsd -gt 1) {
  throw "MaximumSpendUsd must be greater than zero and no more than USD 1.00 for the first acceptance clip."
}
$expected = "SPEND-$($Provider.ToUpperInvariant())-$($MaximumSpendUsd.ToString('0.00'))"
if ($Confirmation -ne $expected) {
  throw "Confirmation mismatch. Re-run with -Confirmation '$expected' only after reviewing the exact approved plan and ceiling."
}
if (-not (Test-Path -LiteralPath $ReservationPayloadFile -PathType Leaf)) {
  throw "Reservation payload file was not found: $ReservationPayloadFile"
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$KeyPath = Join-Path $Runtime "operator-keys.json"
$keys = Get-Content -LiteralPath $KeyPath -Raw | ConvertFrom-Json
$env:PLATFORM_ADMIN_KEY = [string]$keys.'local-admin'
$env:PLATFORM_SUPER_ADMIN_KEY = [string]$keys.'local-super-admin'
$env:PLATFORM_REVIEWER_KEY = [string]$keys.'local-reviewer'
$env:PLATFORM_BASE_URL = $BaseUrl.TrimEnd("/")
$env:PLATFORM_LIVE_PROVIDER_ACCEPTANCE = "true"
$env:PLATFORM_LIVE_PROVIDER = $Provider
$env:PLATFORM_LIVE_ROUTING_PLAN_ID = $RoutingPlanId
$env:PLATFORM_LIVE_RESERVATION_PAYLOAD_FILE = (Resolve-Path $ReservationPayloadFile).Path
$env:PLATFORM_LIVE_MAX_SPEND_USD = $MaximumSpendUsd.ToString("0.00")
$env:PLATFORM_LIVE_CONFIRMATION = $Confirmation
$env:PLATFORM_HEADED = if ($Headed) { "true" } else { "false" }
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$env:PLATFORM_E2E_RUN_ID = "live-provider-$timestamp"
$env:PLATFORM_E2E_RUN_DIR = Join-Path $Runtime "e2e\live-provider-$timestamp"

Push-Location $Root
try {
  & npx playwright test tests/e2e/06-live-provider.spec.js --grep "@live-provider" --workers=1
  if ($LASTEXITCODE -ne 0) { throw "Controlled live-provider acceptance failed." }
} finally {
  Pop-Location
  @(
    "PLATFORM_ADMIN_KEY", "PLATFORM_SUPER_ADMIN_KEY", "PLATFORM_REVIEWER_KEY",
    "PLATFORM_LIVE_PROVIDER_ACCEPTANCE", "PLATFORM_LIVE_PROVIDER",
    "PLATFORM_LIVE_ROUTING_PLAN_ID", "PLATFORM_LIVE_RESERVATION_PAYLOAD_FILE",
    "PLATFORM_LIVE_MAX_SPEND_USD", "PLATFORM_LIVE_CONFIRMATION"
  ) | ForEach-Object { Remove-Item "Env:$_" -ErrorAction SilentlyContinue }
}
Write-Host "Exactly one approved managed job was reserved and enqueued. Complete provider output validation and human review before closing the live-proof issue." -ForegroundColor Yellow
