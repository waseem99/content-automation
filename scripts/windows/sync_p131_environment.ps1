[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$Path
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Path)) { return }

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$values = [ordered]@{}
foreach ($line in Get-Content -LiteralPath $Path) {
  $trimmed = $line.Trim()
  if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
  $parts = $trimmed.Split("=", 2)
  $values[$parts[0]] = $parts[1]
}

$values["OPS_MIGRATION_HEAD"] = "0108_p131_staged_acceptance_closeout.sql"
$values["HYBRID_ROUTING_ENABLED"] = "true"
$values["HYBRID_PAID_EXECUTION_ENABLED"] = "false"
$values["HYBRID_PUBLIC_PUBLISHING_ENABLED"] = "false"
$values["PRE_GENERATION_AUTOPILOT_ENABLED"] = "true"
$values["LOCAL_SCRIPT_TIMEOUT_SECONDS"] = "120"
$values["OPS_MAX_REQUEST_BODY_BYTES"] = "67108864"
# The browser shell and versioned static assets are not protected API calls.
# Keep authentication, operations and every other API route inside the rate window.
$values["OPS_RATE_LIMIT_EXEMPT_PATHS"] = '["/app","/favicon.ico","/health","/runtime/ready"]'
$values["OPS_RATE_LIMIT_EXEMPT_PREFIXES"] = '["/app/","/assets/"]'

# Release evidence must identify the checkout that is actually serving Creator Studio.
# Failure to resolve Git is non-destructive: an existing valid SHA is retained.
if (Get-Command git -ErrorAction SilentlyContinue) {
  try {
    $gitSha = [string](& git -C $Root rev-parse HEAD 2>$null)
    $gitSha = $gitSha.Trim().ToLowerInvariant()
    if ($gitSha -match '^[0-9a-f]{40}$') { $values["OPS_GIT_SHA"] = $gitSha }
  } catch { }
}

# Hash only non-secret runtime configuration. Secret-like values and connection
# strings are excluded so the digest is useful evidence without becoming a
# password/token verifier.
$excluded = '(^|_)(PASSWORD|PASS|SECRET|TOKEN|KEY|CREDENTIAL|DATABASE_URL)($|_)|OPERATOR_API_KEYS_JSON|OPS_CONFIGURATION_DIGEST'
$configurationLines = @(
  $values.Keys |
    Where-Object { [string]$_ -notmatch $excluded } |
    Sort-Object |
    ForEach-Object { "$_=$($values[$_])" }
)
$bytes = [Text.Encoding]::UTF8.GetBytes(($configurationLines -join "`n"))
$hasher = [Security.Cryptography.SHA256]::Create()
try {
  $values["OPS_CONFIGURATION_DIGEST"] = ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
} finally {
  $hasher.Dispose()
}

[IO.File]::WriteAllLines(
  $Path,
  [string[]]@($values.Keys | ForEach-Object { "$_=$($values[$_])" }),
  (New-Object Text.UTF8Encoding($false))
)
