param(
    [switch]$SkipPush
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
$original = [System.IO.File]::ReadAllText($target)

$replacement = @'
def render_animation(renderer: Callable[[float], Image.Image], output: Path, duration_seconds: float) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    frames = max(2, round(duration_seconds * FPS))
    encoded_duration_seconds = frames / FPS
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
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
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-vf",
        "scale=1080:1920:flags=lanczos,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-t",
        f"{encoded_duration_seconds:.6f}",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    try:
        for index in range(frames):
            image = renderer(index / max(frames - 1, 1)).convert("RGB")
            process.stdin.write(image.tobytes())
        process.stdin.close()
        process.stdin = None
        _, stderr_bytes = process.communicate(timeout=max(30, round(encoded_duration_seconds * 20)))
    except subprocess.TimeoutExpired as exc:
        process.kill()
        _, stderr_bytes = process.communicate()
        stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
        raise RuntimeError(f"ffmpeg timed out while rendering {output}\n{stderr[-4000:]}") from exc
    except Exception:
        process.kill()
        process.communicate()
        raise
    stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
    if process.returncode:
        raise RuntimeError(stderr[-4000:])
    return probe_media(output)
'@

$pattern = '(?s)def render_animation\(renderer: Callable\[\[float\], Image\.Image\], output: Path, duration_seconds: float\) -> dict\[str, Any\]:.*?    return probe_media\(output\)'
$updated = [regex]::Replace($original, $pattern, $replacement, 1)

if ($updated -eq $original) {
    if ($original -match 'encoded_duration_seconds = frames / FPS') {
        Write-Host "Windows FFmpeg fix is already present." -ForegroundColor Yellow
    }
    else {
        throw "Expected render_animation block was not found; no file was changed."
    }
}
else {
    [System.IO.File]::WriteAllText($target, $updated, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Patched: src/p68_scientific_animation.py" -ForegroundColor Cyan
}

Write-Host "Running isolated scientific-animation test..." -ForegroundColor Cyan
python -m pytest -vv -x --tb=short tests\unit\test_p68_scientific_animation.py
if ($LASTEXITCODE -ne 0) {
    git checkout -- src/p68_scientific_animation.py
    throw "Scientific-animation test failed. The local code change was reverted."
}

Write-Host "Scientific-animation test passed." -ForegroundColor Green

git add src/p68_scientific_animation.py
if (git diff --cached --quiet) {
    Write-Host "No new renderer change needs committing." -ForegroundColor Yellow
    exit 0
}

git commit -m "Bound scientific animation FFmpeg rendering on Windows"
if ($LASTEXITCODE -ne 0) {
    throw "Could not commit the verified renderer fix."
}

if (-not $SkipPush) {
    git push origin HEAD:local-next-720
    if ($LASTEXITCODE -ne 0) {
        throw "The fix passed locally and was committed, but git push failed."
    }
    Write-Host "Verified renderer fix pushed to local-next-720." -ForegroundColor Green
}
else {
    Write-Host "Verified renderer fix committed locally; push skipped." -ForegroundColor Yellow
}
