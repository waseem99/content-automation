"""Local Kokoro ONNX narration with deterministic evidence and audio normalization."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


PROVIDER = "kokoro-onnx"
MODEL_ID = "hexgrad/Kokoro-82M-v1.0-onnx"
SAMPLE_RATE = 24000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def proportional_alignment(text: str, duration_seconds: float) -> list[dict[str, Any]]:
    words = text.split()
    weights = [max(len(word.strip(".,!?;:")), 1) for word in words]
    total = max(sum(weights), 1)
    cursor = 0.0
    rows = []
    for word, weight in zip(words, weights):
        end = cursor + duration_seconds * weight / total
        rows.append({"word": word, "startSec": round(cursor, 4), "endSec": round(end, 4), "timingBasis": "proportional_estimate"})
        cursor = end
    if rows:
        rows[-1]["endSec"] = round(duration_seconds, 4)
    return rows


def probe_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True, timeout=60,
    )
    return round(float(result.stdout.strip()), 3)


def normalize_narration(source: Path, target: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".partial.wav")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(source), "-af", "loudnorm=I=-16:LRA=7:TP=-1.5", "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(partial)],
        capture_output=True, text=True, check=True, timeout=180,
    )
    partial.replace(target)


def synthesize(*, text: str, model_path: Path, voices_path: Path, voice: str, speed: float, output_path: Path, evidence_path: Path) -> dict[str, Any]:
    if not text.strip():
        raise ValueError("Narration text is required")
    if not 0.5 <= speed <= 2.0:
        raise ValueError("Kokoro speed must be between 0.5 and 2.0")
    if not model_path.is_file() or not voices_path.is_file():
        raise FileNotFoundError("Kokoro model and voices files are required")
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Install the local kokoro-onnx runtime before synthesis") from exc
    engine = Kokoro(str(model_path), str(voices_path))
    samples, sample_rate = engine.create(text, voice=voice, speed=speed, lang="en-us")
    raw = output_path.with_suffix(".raw.wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(raw, samples, sample_rate)
    try:
        normalize_narration(raw, output_path)
    finally:
        raw.unlink(missing_ok=True)
    duration = probe_duration(output_path)
    evidence = {
        "schema_version": "p78.kokoro_narration.v1", "provider": PROVIDER, "model": MODEL_ID,
        "voice": voice, "speed": speed, "sample_rate": SAMPLE_RATE, "durationSeconds": duration,
        "output_path": str(output_path), "output_sha256": sha256_file(output_path),
        "model_sha256": sha256_file(model_path), "voices_sha256": sha256_file(voices_path),
        "license": "Apache-2.0 model; MIT runtime", "alignment": proportional_alignment(text, duration),
        "human_review_required": True, "publish_allowed": False,
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence
