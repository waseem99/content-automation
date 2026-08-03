[CmdletBinding()]
param(
  [switch]$InstallAllBrowsers
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $Root
try {
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js 20 or newer is required. Install the current Node.js LTS release, reopen PowerShell, and rerun."
  }
  $major = [int]((& node --version).TrimStart("v").Split(".")[0])
  if ($major -lt 20) {
    throw "Node.js 20 or newer is required. Current version: $(& node --version)"
  }
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required and was not found on PATH."
  }

  Write-Host "Installing locked browser-acceptance dependencies..." -ForegroundColor Cyan
  & npm install
  if ($LASTEXITCODE -ne 0) { throw "npm install failed." }

  if ($InstallAllBrowsers) {
    & npx playwright install chromium firefox webkit
  } else {
    & npx playwright install chromium
  }
  if ($LASTEXITCODE -ne 0) { throw "Playwright browser installation failed." }

  & npx playwright --version
  if ($LASTEXITCODE -ne 0) { throw "Playwright installation validation failed." }
  Write-Host "Automated platform acceptance is installed." -ForegroundColor Green
} finally {
  Pop-Location
}
