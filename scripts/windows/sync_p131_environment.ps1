[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$Path
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Path)) { return }

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

[IO.File]::WriteAllLines(
  $Path,
  [string[]]@($values.Keys | ForEach-Object { "$_=$($values[$_])" }),
  (New-Object Text.UTF8Encoding($false))
)
