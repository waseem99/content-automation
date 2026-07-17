$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host "`n=== $Label ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot
Write-Host "Validating repository: $repoRoot" -ForegroundColor Green

Invoke-Checked "Python runtime" { python --version }
Invoke-Checked "Node runtime" { node --version }
Invoke-Checked "npm runtime" { npm --version }
Invoke-Checked "Git runtime" { git --version }

Write-Host "`n=== Sensitive tracked-file check ===" -ForegroundColor Cyan
$tracked = git ls-files
$blocked = $tracked | Where-Object {
    $_ -match '(^|/)\.env\.local$' -or
    $_ -match 'facebook-browser' -or
    $_ -match 'content-automation-data' -or
    $_ -match '\.(cookie|cookies)$'
}
if ($blocked) {
    $blocked | ForEach-Object { Write-Error "Sensitive path is tracked: $_" }
    throw "Sensitive local files must not be committed."
}
Write-Host "No blocked credential, cookie, or browser-profile paths are tracked."

Invoke-Checked "Static Creator Studio build" { npm run build }

Write-Host "`n=== JavaScript syntax ===" -ForegroundColor Cyan
$javascriptTargets = @()
if (Test-Path "scripts") {
    $javascriptTargets += Get-ChildItem "scripts" -Recurse -File | Where-Object { $_.Extension -in @('.js', '.mjs') }
}
if (Test-Path "web\static-creator-ui\assets") {
    $javascriptTargets += Get-ChildItem "web\static-creator-ui\assets" -Recurse -File | Where-Object { $_.Extension -in @('.js', '.mjs') }
}
foreach ($target in $javascriptTargets) {
    node --check $target.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "JavaScript syntax failed: $($target.FullName)"
    }
}
Write-Host "JavaScript syntax passed for $($javascriptTargets.Count) files."

Invoke-Checked "Python compilation" {
    python -m compileall -q src scripts reference-engine\refintel
}

$testPaths = @(
    "tests\unit\test_p68_batch_preflight.py",
    "tests\unit\test_p68_candidate_selection.py",
    "tests\unit\test_p68_clip_generator.py",
    "tests\unit\test_p68_clip_stitcher.py",
    "tests\unit\test_p68_generation_governance.py",
    "tests\unit\test_p68_hybrid_review.py",
    "tests\unit\test_p68_job_state.py",
    "tests\unit\test_p68_keyframe_batch.py",
    "tests\unit\test_p68_keyframe_generator.py",
    "tests\unit\test_p68_keyframe_provider.py",
    "tests\unit\test_p68_motion_batch.py",
    "tests\unit\test_p68_pilot_batch.py",
    "tests\unit\test_p68_production_pipeline.py",
    "tests\unit\test_p68_rn_worker_package.py",
    "tests\unit\test_p68_scientific_animation.py",
    "tests\unit\test_p68_video_provider.py",
    "tests\unit\test_p78_kokoro_narration.py",
    "tests\unit\test_p79_month_factory.py",
    "tests\unit\test_p81_high_volume_calendar.py",
    "tests\unit\test_p82_portfolio_calendar.py",
    "tests\integration\test_p69_portfolio_content_engine.py",
    "tests\integration\test_p71_portfolio_staging.py",
    "tests\integration\test_p72_month_inventory.py",
    "tests\integration\test_p74_facebook_reference_pipeline.py",
    "tests\integration\test_p75_cross_platform_reference_intelligence.py",
    "tests\integration\test_p75_portfolio_reference_ui.py",
    "tests\integration\test_p76_portfolio_generation_bridge.py",
    "tests\integration\test_p76_portfolio_review_workspace.py",
    "tests\integration\test_p77_gecko_visual_review.py",
    "tests\integration\test_p79_four_brand_month_factory.py",
    "tests\integration\test_p80_brand_month_studio.py"
)

$missingTests = $testPaths | Where-Object { -not (Test-Path $_) }
if ($missingTests) {
    $missingTests | ForEach-Object { Write-Error "Missing test file: $_" }
    throw "One or more reconciliation test files are missing."
}

Invoke-Checked "Focused P68-P82 contract tests" {
    python -m pytest -q @testPaths
}

$resultPath = Join-Path $repoRoot "local-reconciliation-validation.txt"
@"
SELF-HOSTED RECONCILIATION VALIDATION: PASSED
Validated at (UTC): $([DateTime]::UtcNow.ToString('o'))
Repository: $repoRoot
Static build: passed
JavaScript syntax: passed
Python compilation: passed
Focused P68-P82 tests: passed
Sensitive tracked-file check: passed
GitHub-hosted compute: not used
Artifacts uploaded: none
"@ | Set-Content -Encoding UTF8 $resultPath

Write-Host "`nVALIDATION PASSED" -ForegroundColor Green
Write-Host "Result written to: $resultPath" -ForegroundColor Green
