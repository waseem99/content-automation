[CmdletBinding(SupportsShouldProcess)]
param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$EnvPath = Join-Path $Root ".env.local"
$KeyPath = Join-Path $Runtime "operator-keys.json"
$RotationRecord = Join-Path $Runtime "operator-key-rotation.json"
$PublicOperators = @(
  "local-super-admin",
  "local-admin",
  "local-reviewer",
  "local-producer",
  "local-publisher"
)

function New-OperatorSecret([int]$Bytes = 32) {
  $buffer = New-Object byte[] $Bytes
  $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
  try { $generator.GetBytes($buffer) } finally { $generator.Dispose() }
  return ([Convert]::ToBase64String($buffer)).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Read-DotEnv([string]$Path) {
  $values = [ordered]@{}
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
    $parts = $trimmed.Split("=", 2)
    $values[[string]$parts[0]] = [string]$parts[1]
  }
  return $values
}

function Write-Utf8Atomic([string]$Path, [string[]]$Lines) {
  $directory = Split-Path -Parent $Path
  New-Item -ItemType Directory -Force -Path $directory | Out-Null
  $temporary = Join-Path $directory ".$(Split-Path -Leaf $Path).$([guid]::NewGuid().ToString('N')).tmp"
  try {
    [IO.File]::WriteAllLines($temporary, $Lines, (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporary -Destination $Path -Force
  } finally {
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
  }
}

if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) {
  throw "Local environment file is missing: $EnvPath"
}
if (-not $Force -and -not $PSCmdlet.ShouldProcess($EnvPath, "Rotate local Super Admin, Admin and Reviewer keys")) {
  return
}

$values = Read-DotEnv $EnvPath
$pairs = [ordered]@{}
$raw = [string]$values["OPERATOR_API_KEYS_JSON"]
if ($raw) {
  try {
    $parsed = $raw | ConvertFrom-Json
    foreach ($property in $parsed.PSObject.Properties) {
      $pairs[[string]$property.Name] = [string]$property.Value
    }
  } catch {
    throw "OPERATOR_API_KEYS_JSON is not valid JSON. Rotation stopped without changing files."
  }
}

$next = [ordered]@{}
foreach ($entry in $pairs.GetEnumerator()) {
  if ([string]$entry.Value -notin $PublicOperators) {
    $next[[string]$entry.Key] = [string]$entry.Value
  }
}

$readable = [ordered]@{}
foreach ($operatorId in @("local-super-admin", "local-admin", "local-reviewer")) {
  do { $newKey = New-OperatorSecret } while ($next.Contains($newKey))
  $next[$newKey] = $operatorId
  $readable[$operatorId] = $newKey
}
foreach ($entry in $next.GetEnumerator()) {
  if (-not $readable.Contains([string]$entry.Value)) {
    $readable[[string]$entry.Value] = [string]$entry.Key
  }
}

$values["OPERATOR_API_KEYS_JSON"] = ($next | ConvertTo-Json -Compress)
Write-Utf8Atomic $EnvPath ([string[]]@($values.Keys | ForEach-Object { "$_=$($values[$_])" }))
Write-Utf8Atomic $KeyPath ([string[]]@(($readable | ConvertTo-Json -Depth 4).Split([Environment]::NewLine)))

$record = [ordered]@{
  kind = "local_operator_key_rotation"
  rotated_at = (Get-Date).ToUniversalTime().ToString("o")
  rotated_operator_ids = @("local-super-admin", "local-admin", "local-reviewer")
  preserved_non_public_operator_count = [Math]::Max(0, $next.Count - 3)
  secret_values_recorded = $false
  restart_required = $true
}
Write-Utf8Atomic $RotationRecord ([string[]]@(($record | ConvertTo-Json -Depth 4).Split([Environment]::NewLine)))

Write-Host "Local operator keys were rotated atomically." -ForegroundColor Green
Write-Host "Restart or redeploy Creator Studio immediately so the new keys become active." -ForegroundColor Yellow
Write-Host "The replacement values were written only to .runtime\operator-keys.json and were not printed." -ForegroundColor Yellow
