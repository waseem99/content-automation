[CmdletBinding()]
param(
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root ".runtime\p113"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

if (-not $OutputPath) {
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $OutputPath = Join-Path $Runtime "hardware-snapshot-$stamp.json"
} elseif (-not [IO.Path]::IsPathRooted($OutputPath)) {
  $OutputPath = Join-Path $Root $OutputPath
}

function First-Line([scriptblock]$Command) {
  try {
    $result = & $Command 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $result) { return $null }
    return [string](@($result)[0])
  } catch {
    return $null
  }
}

function Parse-NullableNumber([string]$Value) {
  $number = 0.0
  if ([double]::TryParse($Value.Trim(), [ref]$number)) { return $number }
  return $null
}

$os = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
$processors = @(Get-CimInstance Win32_Processor | ForEach-Object {
  [ordered]@{
    name = [string]$_.Name
    physical_cores = [int]$_.NumberOfCores
    logical_processors = [int]$_.NumberOfLogicalProcessors
    max_clock_mhz = [int]$_.MaxClockSpeed
  }
})

$gpus = @()
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  $rows = @(& nvidia-smi `
    --query-gpu=name,driver_version,memory.total,temperature.gpu,power.draw,power.limit `
    --format=csv,noheader,nounits 2>$null)
  foreach ($row in $rows) {
    $parts = @($row -split "," | ForEach-Object { $_.Trim() })
    if ($parts.Count -ge 6) {
      $gpus += [ordered]@{
        name = $parts[0]
        driver_version = $parts[1]
        memory_total_mib = Parse-NullableNumber $parts[2]
        temperature_c = Parse-NullableNumber $parts[3]
        power_draw_w = Parse-NullableNumber $parts[4]
        power_limit_w = Parse-NullableNumber $parts[5]
      }
    }
  }
}

$disks = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
  [ordered]@{
    filesystem = [string]$_.FileSystem
    size_bytes = if ($_.Size) { [int64]$_.Size } else { $null }
    free_bytes = if ($_.FreeSpace) { [int64]$_.FreeSpace } else { $null }
  }
})

$comfy = [ordered]@{
  endpoint = "http://127.0.0.1:8188"
  reachable = $false
  system_stats_available = $false
}
try {
  $stats = Invoke-RestMethod -Uri "$($comfy.endpoint)/system_stats" -TimeoutSec 3
  $comfy.reachable = $true
  $comfy.system_stats_available = $true
  $comfy.devices = @($stats.devices | ForEach-Object {
    [ordered]@{
      name = [string]$_.name
      type = [string]$_.type
      vram_total = $_.vram_total
      vram_free = $_.vram_free
    }
  })
} catch {
  try {
    Invoke-WebRequest -UseBasicParsing -Uri $comfy.endpoint -TimeoutSec 3 | Out-Null
    $comfy.reachable = $true
  } catch {
    $comfy.reachable = $false
  }
}

Push-Location $Root
try {
  $gitSha = First-Line { git rev-parse HEAD }
  $gitBranch = First-Line { git branch --show-current }
} finally {
  Pop-Location
}

$snapshot = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  snapshot_kind = "p113_workstation_hardware"
  workstation = [ordered]@{
    manufacturer = [string]$computer.Manufacturer
    model = [string]$computer.Model
    total_physical_memory_bytes = [int64]$computer.TotalPhysicalMemory
    os_caption = [string]$os.Caption
    os_version = [string]$os.Version
    os_build = [string]$os.BuildNumber
    processors = $processors
    gpus = $gpus
    disks = $disks
  }
  software = [ordered]@{
    git_sha = $gitSha
    git_branch = $gitBranch
    python = First-Line { python --version }
    docker = First-Line { docker --version }
    ffmpeg = First-Line { ffmpeg -version }
    comfyui = $comfy
  }
  measurement_notes = @(
    "This is a point-in-time inventory snapshot, not a throughput benchmark.",
    "Machine names, disk letters, GPU UUIDs, environment variables and credentials are omitted.",
    "Sustained temperature, power, VRAM and timing are recorded per generation attempt."
  )
}

$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$snapshot | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding utf8

Write-Host "P113 hardware snapshot created:" -ForegroundColor Green
Write-Host $OutputPath
