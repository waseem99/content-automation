[CmdletBinding()]
param(
  [int]$ApiPort = 8000,
  [switch]$RequireRemoteAccess,
  [switch]$RequireHiggsfield
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$KeyPath = Join-Path $Runtime "operator-keys.json"
$HeartbeatPath = Join-Path $Runtime "supervisor-heartbeat.json"
$RemotePath = Join-Path $Runtime "remote-access.json"
$HiggsfieldPath = Join-Path $Runtime "higgsfield-readiness.json"
$ReportPath = Join-Path $Runtime "production-readiness.json"

$checks = [ordered]@{}
$checks["runtime_directory"] = Test-Path $Runtime
$checks["operator_keys"] = Test-Path $KeyPath
$checks["supervisor_heartbeat"] = Test-Path $HeartbeatPath
$checks["artifact_directory"] = Test-Path (Join-Path $Runtime "artifacts")
$checks["backup_directory"] = Test-Path (Join-Path $Runtime "backups")
$checks["docker"] = [bool](Get-Command docker -ErrorAction SilentlyContinue)
$checks["ollama"] = [bool](Get-Command ollama -ErrorAction SilentlyContinue)
$checks["ffmpeg"] = [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue)
$checks["ngrok"] = [bool](Get-Command ngrok -ErrorAction SilentlyContinue)

try {
  $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/runtime/ready" -TimeoutSec 8
  $checks["api_ready"] = [bool]$ready.ok
  $checks["database_reachable"] = [bool]$ready.checks.database_reachable
  $checks["migrations_ready"] = [bool]$ready.checks.migrations_ready
} catch {
  $checks["api_ready"] = $false
  $checks["database_reachable"] = $false
  $checks["migrations_ready"] = $false
}

$roleResults = [ordered]@{}
if (Test-Path $KeyPath) {
  $keys = Get-Content -LiteralPath $KeyPath -Raw | ConvertFrom-Json
  foreach ($role in @("local-super-admin", "local-admin", "local-reviewer")) {
    $key = [string]$keys.$role
    if (-not $key) {
      $roleResults[$role] = @{ ok = $false; reason = "missing_key" }
      continue
    }
    try {
      $access = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/access/me" -Headers @{ "X-Operator-Key" = $key } -TimeoutSec 8
      $internal = @($access.operator.roles)
      $valid = switch ($role) {
        "local-super-admin" { $internal -contains "super_admin" -and $internal -contains "admin" }
        "local-admin" { $internal -contains "admin" -and $internal -notcontains "super_admin" }
        "local-reviewer" { $internal -contains "reviewer" -and $internal -contains "producer" -and $internal -contains "publisher" }
      }
      $roleResults[$role] = @{
        ok = [bool]$valid
        portfolio_wide = [bool]$access.operator.portfolio_wide
        internal_roles = $internal
      }
    } catch {
      $roleResults[$role] = @{ ok = $false; reason = "access_check_failed" }
    }
  }
}
$checks["three_role_model"] = @($roleResults.Values | Where-Object { -not $_.ok }).Count -eq 0 -and $roleResults.Count -eq 3

$remote = $null
if (Test-Path $RemotePath) {
  $remote = Get-Content -LiteralPath $RemotePath -Raw | ConvertFrom-Json
  try {
    $remoteReady = Invoke-RestMethod -Uri "$($remote.public_url)/runtime/ready" -Headers @{ "ngrok-skip-browser-warning" = "true" } -TimeoutSec 15
    $checks["remote_https_ready"] = [bool]$remoteReady.ok
  } catch {
    $checks["remote_https_ready"] = $false
  }
} else {
  $checks["remote_https_ready"] = -not $RequireRemoteAccess
}

$higgsfield = $null
if (Test-Path $HiggsfieldPath) {
  $higgsfield = Get-Content -LiteralPath $HiggsfieldPath -Raw | ConvertFrom-Json
  $checks["higgsfield_account_ready"] = [bool]$higgsfield.interactive_auth_completed
} else {
  $checks["higgsfield_account_ready"] = -not $RequireHiggsfield
}

$failed = @($checks.GetEnumerator() | Where-Object { $_.Value -ne $true } | ForEach-Object { $_.Key })
$report = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  ready = $failed.Count -eq 0
  checks = $checks
  roles = $roleResults
  failed_checks = $failed
  remote_url = if ($remote) { [string]$remote.public_url } else { $null }
  higgsfield_authenticated = if ($higgsfield) { [bool]$higgsfield.interactive_auth_completed } else { $false }
  automatic_approval = $false
  live_publishing_validated = $false
  p100_real_pilot_completed = $false
  six_video_benchmark_completed = $false
}
$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ReportPath -Encoding utf8

if ($report.ready) {
  Write-Host "Workstation runtime readiness passed." -ForegroundColor Green
} else {
  Write-Host "Workstation readiness is blocked by: $($failed -join ', ')" -ForegroundColor Yellow
}
Write-Host "Report: $ReportPath"
if (-not $report.ready) { exit 1 }
