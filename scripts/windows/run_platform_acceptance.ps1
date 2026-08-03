[CmdletBinding()]
param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$RemoteUrl = "",
  [switch]$Headed,
  [switch]$CrossBrowser,
  [switch]$Mutating,
  [switch]$Smoke,
  [switch]$SkipBackup,
  [switch]$OpenReport
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$KeyPath = Join-Path $Runtime "operator-keys.json"
$EnvPath = Join-Path $Root ".env.local"
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$RunId = "platform-$timestamp"
$RunDir = Join-Path $Runtime "e2e\$RunId"
$Latest = Join-Path $Runtime "e2e\latest"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Read-DotEnv([string]$Path) {
  $result = @{}
  foreach ($line in Get-Content -LiteralPath $Path) {
    $value = $line.Trim()
    if (-not $value -or $value.StartsWith("#") -or -not $value.Contains("=")) { continue }
    $parts = $value.Split("=", 2)
    $result[$parts[0]] = $parts[1]
  }
  return $result
}

function Assert-Disabled([hashtable]$Values, [string]$Name) {
  $value = [string]$Values[$Name]
  if ($value -and $value.Trim().ToLowerInvariant() -notin @("0", "false", "no", "off")) {
    throw "$Name must be disabled for no-cost platform acceptance. Current value: $value"
  }
}

if (-not (Test-Path -LiteralPath $KeyPath)) { throw "Operator keys are missing: $KeyPath" }
if (-not (Test-Path -LiteralPath $EnvPath)) { throw "Local environment is missing: $EnvPath" }
$values = Read-DotEnv $EnvPath
Assert-Disabled $values "PROVIDER_PAID_EXECUTION_ENABLED"
Assert-Disabled $values "HYBRID_PAID_EXECUTION_ENABLED"
Assert-Disabled $values "HYBRID_PUBLIC_PUBLISHING_ENABLED"

$ready = Invoke-RestMethod -Uri "$BaseUrl/runtime/ready" -TimeoutSec 15
if (-not $ready.ok) { throw "Local runtime readiness is false." }
if ($RemoteUrl) {
  $remote = Invoke-RestMethod -Uri "$RemoteUrl/runtime/ready" -Headers @{ "ngrok-skip-browser-warning" = "true" } -TimeoutSec 20
  if (-not $remote.ok) { throw "Remote runtime readiness is false." }
}

$keys = Get-Content -LiteralPath $KeyPath -Raw | ConvertFrom-Json
$admin = [string]$keys.'local-admin'
$superAdmin = [string]$keys.'local-super-admin'
$reviewer = [string]$keys.'local-reviewer'
if (-not $admin) { throw "local-admin key is missing." }

if (-not $SkipBackup -and $Mutating) {
  $backup = Join-Path $RunDir "pre-run-postgres.dump"
  Push-Location $Root
  try {
    $command = "docker compose --env-file .env.local -f compose.local.yml exec -T postgres pg_dump -U postgres -Fc content_automation > `"$backup`""
    & cmd.exe /d /s /c $command
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $backup)) {
      throw "Pre-run PostgreSQL backup failed."
    }
  } finally {
    Pop-Location
  }
}

if (Test-Path -LiteralPath $Latest) {
  Remove-Item -LiteralPath $Latest -Force
}
New-Item -ItemType Junction -Path $Latest -Target $RunDir | Out-Null

$env:PLATFORM_BASE_URL = $BaseUrl.TrimEnd("/")
$env:PLATFORM_REMOTE_URL = $RemoteUrl.TrimEnd("/")
$env:PLATFORM_ADMIN_KEY = $admin
$env:PLATFORM_SUPER_ADMIN_KEY = $superAdmin
$env:PLATFORM_REVIEWER_KEY = $reviewer
$env:PLATFORM_E2E_RUN_ID = $RunId
$env:PLATFORM_E2E_RUN_DIR = $RunDir
$env:PLATFORM_E2E_MUTATING = if ($Mutating) { "true" } else { "false" }
$env:PLATFORM_CROSS_BROWSER = if ($CrossBrowser) { "true" } else { "false" }
$env:PLATFORM_HEADED = if ($Headed) { "true" } else { "false" }

Push-Location $Root
try {
  if (-not (Test-Path (Join-Path $Root "node_modules\@playwright\test"))) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "install_platform_acceptance.ps1") -InstallAllBrowsers:$CrossBrowser
    if ($LASTEXITCODE -ne 0) { throw "Playwright installation failed." }
  }

  $arguments = @("playwright", "test")
  if ($Smoke) { $arguments += @("--grep", "@smoke") }
  & npx @arguments
  $exitCode = $LASTEXITCODE
} finally {
  Pop-Location
  Remove-Item Env:PLATFORM_ADMIN_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:PLATFORM_SUPER_ADMIN_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:PLATFORM_REVIEWER_KEY -ErrorAction SilentlyContinue
}

Write-Host "Acceptance evidence: $RunDir" -ForegroundColor Cyan
Write-Host "Summary: $(Join-Path $RunDir 'summary.md')"
Write-Host "HTML report: $(Join-Path $RunDir 'playwright-report\index.html')"
if ($OpenReport -and (Test-Path (Join-Path $RunDir "playwright-report\index.html"))) {
  Start-Process (Join-Path $RunDir "playwright-report\index.html")
}
if ($exitCode -ne 0) { throw "Platform acceptance failed. Review defects.md and the HTML report." }
Write-Host "Platform acceptance passed for the configured scope." -ForegroundColor Green
