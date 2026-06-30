"""ffmpeg utilities: probe duration, extract audio, cut clips."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClipWindow:
    start: float
    end: float
    score: float = 0.0
    label: str = "moment"
    source_text: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def slugify_label(label: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return slug[:max_len] or "moment"


def is_valid_audio_file(audio_path: Path, min_bytes: int = 1024) -> bool:
    if not audio_path.exists() or audio_path.stat().st_size < min_bytes:
        return False
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return False
    return duration > 0


def probe_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def extract_audio_wav(video_path: Path, wav_path: Path, max_duration: float | None = None) -> Path:
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
    ]
    if max_duration is not None:
        cmd.extend(["-t", str(max_duration)])
    cmd.extend(
        [
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
    )
    subprocess.run(cmd, capture_output=True, check=True)
    return wav_path


def extract_clip(
    video_path: Path,
    output_path: Path,
    start: float,
    end: float,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-to",
        f"{end:.3f}",
        "-i",
        str(video_path),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def extract_clips(
    video_path: Path,
    output_dir: Path,
    windows: list[ClipWindow],
) -> list[Path]:
    paths: list[Path] = []
    for index, window in enumerate(windows, start=1):
        label = slugify_label(window.label)
        filename = f"clip_{index:02d}_{label}.mp4"
        path = extract_clip(video_path, output_dir / filename, window.start, window.end)
        paths.append(path)
    return paths
