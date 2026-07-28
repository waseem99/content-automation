[CmdletBinding()]
param(
  [switch]$SkipComfyUI,
  [switch]$AcceptComfyModelLicense,
  [switch]$SkipInstall,
  [switch]$SkipModelPull,
  [int]$ApiPort = 8000
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime"
$Deploy = Join-Path $PSScriptRoot "deploy_always_on_local_production.ps1"
$RemoteStatus = Join-Path $Runtime "remote-access.json"

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
  throw "ngrok is required. Install ngrok, run 'ngrok config add-authtoken <token>', then rerun."
}

# A configured account is required. The command reveals no token.
& ngrok config check 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "ngrok is installed but not configured. Run 'ngrok config add-authtoken <token>' first."
}

$arguments = @(
  "-NoProfile",
  "-ExecutionPolicy", "Bypass",
  "-File", $Deploy,
  "-ExposeWithNgrok"
)
if (-not $SkipComfyUI) { $arguments += "-EnableComfyUI" }
if ($AcceptComfyModelLicense) { $arguments += "-AcceptComfyModelLicense" }
if ($SkipInstall) { $arguments += "-SkipInstall" }
if ($SkipModelPull) { $arguments += "-SkipModelPull" }

$deployment = Start-Process powershell -ArgumentList $arguments -WorkingDirectory $Root -Wait -PassThru
if ($deployment.ExitCode -ne 0) {
  throw "Remote Content Automation deployment failed. Inspect .runtime\logs."
}

$deadline = (Get-Date).AddMinutes(2)
$publicUrl = $null
do {
  Start-Sleep -Seconds 2
  try {
    $localReady = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/runtime/ready" -TimeoutSec 5
    if (-not $localReady.ok) { continue }
    $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5
    $httpsTunnel = @($tunnels.tunnels | Where-Object { $_.proto -eq "https" }) | Select-Object -First 1
    if ($httpsTunnel) { $publicUrl = [string]$httpsTunnel.public_url }
  } catch {
    $publicUrl = $null
  }
} until ($publicUrl -or (Get-Date) -gt $deadline)

if (-not $publicUrl) {
  throw "The local runtime started but no HTTPS ngrok tunnel was discovered. Inspect .runtime\logs\ngrok.error.log."
}

try {
  $remoteReady = Invoke-RestMethod -Uri "$publicUrl/runtime/ready" -TimeoutSec 15
  if (-not $remoteReady.ok) { throw "Remote readiness returned false." }
} catch {
  throw "The ngrok URL exists but the authenticated Creator Studio runtime is not reachable: $($_.Exception.Message)"
}

$status = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  public_url = $publicUrl
  creator_studio_url = "$publicUrl/app/dashboard"
  local_url = "http://127.0.0.1:$ApiPort/app/dashboard"
  authentication_required = $true
  exposed_service = "creator-studio-api-only"
  postgres_exposed = $false
  ollama_exposed = $false
  comfyui_exposed = $false
  artifact_directory_exposed = $false
  role_model = @("super_admin", "admin", "reviewer")
  operator_keys_path = ".runtime/operator-keys.json"
}
$status | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $RemoteStatus -Encoding utf8

Write-Host "" 
Write-Host "Remote Content Automation is ready." -ForegroundColor Green
Write-Host "Creator Studio: $publicUrl/app/dashboard" -ForegroundColor Green
Write-Host "Operator keys:  $Runtime\operator-keys.json"
Write-Host "Remote status:  $RemoteStatus"
Write-Host "Share only the HTTPS Creator Studio URL and the intended user's key. Never share the Super Admin key." -ForegroundColor Yellow
