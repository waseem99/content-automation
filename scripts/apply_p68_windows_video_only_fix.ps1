param(
    [switch]$SkipPush,
    [int]$TestTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$branch = (git branch --show-current).Trim()
if ($branch -ne "local-next-720") {
    throw "Run this script from local-next-720. Current branch: $branch"
}

$target = Join-Path $repoRoot "src\p68_scientific_animation.py"
$testPath = "tests\unit\test_p68_scientific_animation.py"
$original = [System.IO.File]::ReadAllText($target)

$replacement = @'
def render_animation(renderer: Callable[[float], Image.Image], output: Path, duration_seconds: float) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    frames = max(2, round(duration_seconds * FPS))
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{CANVAS[0]}x{CANVAS[1]}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-vf",
        "scale=1080:1920:flags=lanczos,format=yuv420p",
        "-frames:v",
        str(frames),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdin is not None
    try:
        for index in range(frames):
            image = renderer(index / max(frames - 1, 1)).convert("RGB")
            process.stdin.write(image.tobytes())
        process.stdin.close()
        process.stdin = None
        code = process.wait(timeout=max(30, round((frames / FPS) * 20)))
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise RuntimeError(f"ffmpeg timed out while rendering {output}") from exc
    except Exception:
        process.kill()
        process.wait()
        raise
    if code:
        raise RuntimeError(f"ffmpeg exited with code {code} while rendering {output}")
    return probe_media(output)
'@

$pattern = '(?s)def render_animation\(renderer: Callable\[\[float\], Image\.Image\], output: Path, duration_seconds: float\) -> dict\[str, Any\]:.*?    return probe_media\(output\)'
$updated = [regex]::Replace($original, $pattern, $replacement, 1)
$updated = $updated.Replace('ANIMATION_VERSION = "p68.scientific_animation.v4"', 'ANIMATION_VERSION = "p68.scientific_animation.v5"')

if ($updated -eq $original) {
    if ($original -match '"-frames:v"' -and $original -match 'p68\.scientific_animation\.v5') {
        Write-Host "Video-only Windows renderer fix is already present." -ForegroundColor Yellow
    }
    else {
        throw "Expected render_animation block was not found; no file was changed."
    }
}
else {
    [System.IO.File]::WriteAllText($target, $updated, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Patched scientific renderer to exact-frame video-only output." -ForegroundColor Cyan
}

Write-Host "Running isolated scientific-animation test. The renderer has its own bounded FFmpeg timeout." -ForegroundColor Cyan
& python -m pytest -vv -x --tb=short $testPath
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    git checkout -- src/p68_scientific_animation.py
    throw "Scientific-animation test failed with exit code $exitCode. The source change was reverted."
}

Write-Host "Scientific-animation test passed." -ForegroundColor Green

git add src/p68_scientific_animation.py
if (git diff --cached --quiet) {
    Write-Host "No new renderer change needs committing." -ForegroundColor Yellow
    exit 0
}

git commit -m "Make scientific animation rendering finite on Windows"
if ($LASTEXITCODE -ne 0) {
    throw "Could not commit the verified renderer fix."
}

if (-not $SkipPush) {
    git push origin HEAD:local-next-720
    if ($LASTEXITCODE -ne 0) {
        throw "The fix passed locally and was committed, but git push failed."
    }
    Write-Host "Verified video-only renderer fix pushed to local-next-720." -ForegroundColor Green
}
else {
    Write-Host "Verified renderer fix committed locally; push skipped." -ForegroundColor Yellow
}
