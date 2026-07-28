[CmdletBinding()]
param(
  [switch]$InstallSkills
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$StatusPath = Join-Path $Runtime "higgsfield-readiness.json"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "Node.js/npm is required for the official Higgsfield CLI. Install Node.js LTS and rerun."
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

if ($InstallSkills) {
  & npx skills add higgsfield-ai/skills
  if ($LASTEXITCODE -ne 0) { throw "Higgsfield companion skill installation failed." }
}

$status = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  official_cli_installed = $true
  interactive_auth_completed = $true
  credential_stored_outside_git = $true
  mcp_endpoint = "https://mcp.higgsfield.ai/mcp"
  external_spend_enabled = $false
  real_generation_validated = $false
  next_gate = "Approve one quoted managed shot in Creator Studio before any credit-consuming generation."
}
$status | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatusPath -Encoding utf8

Write-Host "Higgsfield account setup completed." -ForegroundColor Green
Write-Host "Readiness record: $StatusPath"
Write-Host "No generation or credit spend was triggered." -ForegroundColor Yellow
