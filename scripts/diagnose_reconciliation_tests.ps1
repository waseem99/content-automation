param(
    [int]$PerFileTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$validationScript = Join-Path $PSScriptRoot "run_reconciliation_validation.ps1"
$diagnosticRoot = Join-Path $env:USERPROFILE "Desktop\reconciliation-test-diagnostics"

New-Item -ItemType Directory -Force -Path $diagnosticRoot | Out-Null
Set-Location $repoRoot

if (-not (Test-Path $validationScript)) {
    throw "Validation script is missing: $validationScript"
}

$scriptText = Get-Content $validationScript -Raw
$matches = [regex]::Matches($scriptText, '"(tests\\[^"\r\n]+\.py)"')
$testPaths = @($matches | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique)

if ($testPaths.Count -eq 0) {
    throw "No reconciliation test files were found in $validationScript"
}

Write-Host "Repository: $repoRoot" -ForegroundColor Cyan
Write-Host "Diagnostic logs: $diagnosticRoot" -ForegroundColor Cyan
Write-Host "Per-file timeout: $PerFileTimeoutSeconds seconds" -ForegroundColor Cyan
Write-Host "Test files: $($testPaths.Count)" -ForegroundColor Cyan

$summary = @()

for ($index = 0; $index -lt $testPaths.Count; $index++) {
    $testPath = $testPaths[$index]
    $safeName = ($testPath -replace '[\\/:*?"<>|]', '_')
    $stdoutPath = Join-Path $diagnosticRoot "$safeName.stdout.log"
    $stderrPath = Join-Path $diagnosticRoot "$safeName.stderr.log"

    Remove-Item $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

    Write-Host "`n[$($index + 1)/$($testPaths.Count)] $testPath" -ForegroundColor Yellow

    $arguments = @(
        '-m', 'pytest',
        '-vv',
        '-x',
        '--tb=short',
        $testPath
    )

    $process = Start-Process `
        -FilePath "python" `
        -ArgumentList $arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru `
        -NoNewWindow

    $completed = $process.WaitForExit($PerFileTimeoutSeconds * 1000)

    if (-not $completed) {
        Write-Host "TIMEOUT: $testPath" -ForegroundColor Red
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        $summary += [PSCustomObject]@{
            Test = $testPath
            Result = 'TIMEOUT'
            ExitCode = $null
        }

        Get-Content $stdoutPath -Tail 80 -ErrorAction SilentlyContinue
        Get-Content $stderrPath -Tail 80 -ErrorAction SilentlyContinue

        $summary | Format-Table -AutoSize
        throw "Diagnostic stopped because $testPath exceeded $PerFileTimeoutSeconds seconds."
    }

    # Windows PowerShell can leave ExitCode unset after the timed WaitForExit overload.
    # A parameterless wait plus Refresh guarantees that the final native exit code is loaded.
    $process.WaitForExit()
    $process.Refresh()
    $exitCode = [int]$process.ExitCode
    $result = if ($exitCode -eq 0) { 'PASSED' } else { 'FAILED' }
    $summary += [PSCustomObject]@{
        Test = $testPath
        Result = $result
        ExitCode = $exitCode
    }

    if ($exitCode -ne 0) {
        Write-Host "FAILED: $testPath (exit code $exitCode)" -ForegroundColor Red
        Get-Content $stdoutPath -Tail 120 -ErrorAction SilentlyContinue
        Get-Content $stderrPath -Tail 120 -ErrorAction SilentlyContinue
        $summary | Format-Table -AutoSize
        throw "Diagnostic stopped at the first failing test file."
    }

    Write-Host "PASSED: $testPath" -ForegroundColor Green
}

$summaryPath = Join-Path $diagnosticRoot "summary.txt"
$summary | Format-Table -AutoSize | Out-String | Set-Content -Encoding UTF8 $summaryPath

Write-Host "`nALL RECONCILIATION TEST FILES PASSED" -ForegroundColor Green
Write-Host "Summary: $summaryPath" -ForegroundColor Green
