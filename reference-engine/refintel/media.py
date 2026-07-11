from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageStat

from .models import FrameArtifact, MediaMetadata, SceneArtifact


SUPPORTED_MEDIA = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def require_binary(name: str) -> str:
    binary = shutil.which(name)
    if not binary:
        raise RuntimeError(f"Required binary not found on PATH: {name}")
    return binary


def run_command(command: list[str], *, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )


def find_source_media(workspace: Path) -> Path:
    candidates = [
        path
        for path in (workspace / "source").iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA
    ]
    if not candidates:
        raise FileNotFoundError("No source media found in the reference workspace")
    return max(candidates, key=lambda item: item.stat().st_size)


def _parse_fraction(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def probe_media(path: Path) -> tuple[MediaMetadata, dict[str, Any]]:
    ffprobe = require_binary("ffprobe")
    result = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    raw = json.loads(result.stdout)
    streams = raw.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if width and height:
        if abs(width - height) <= max(width, height) * 0.08:
            orientation = "square"
        else:
            orientation = "portrait" if height > width else "landscape"
    else:
        orientation = "unknown"
    duration = float(raw.get("format", {}).get("duration") or video.get("duration") or 0)
    metadata = MediaMetadata(
        duration_seconds=duration,
        width=width,
        height=height,
        fps=_parse_fraction(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        video_codec=video.get("codec_name"),
        audio_codec=audio.get("codec_name"),
        bitrate=int(raw.get("format", {}).get("bit_rate") or 0) or None,
        orientation=orientation,
    )
    return metadata, raw


def normalize_media(source: Path, workspace: Path) -> tuple[Path, Path, MediaMetadata]:
    ffmpeg = require_binary("ffmpeg")
    media_dir = workspace / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    proxy = media_dir / "analysis.mp4"
    audio = media_dir / "audio.wav"
    thumbnail = media_dir / "thumbnail.jpg"
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            "scale='min(1280,iw)':-2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(proxy),
        ]
    )
    audio_command = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(audio),
    ]
    audio_result = subprocess.run(audio_command, capture_output=True, text=True, timeout=1800)
    if audio_result.returncode != 0:
        audio.touch()
    run_command(
        [
            ffmpeg,
            "-y",
            "-ss",
            "0.5",
            "-i",
            str(proxy),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(thumbnail),
        ]
    )
    metadata, raw = probe_media(proxy)
    (media_dir / "media_metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "p66.media_metadata.v1",
                "measured": metadata.model_dump(mode="json"),
                "ffprobe": raw,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return proxy, audio, metadata


def interval_timestamps(duration_seconds: float, interval_seconds: int = 60) -> list[float]:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero")
    if duration_seconds <= 0:
        return [0.0]
    count = int(math.floor(duration_seconds / interval_seconds))
    timestamps = [float(index * interval_seconds) for index in range(count + 1)]
    if timestamps and timestamps[-1] >= duration_seconds:
        timestamps[-1] = max(0.0, duration_seconds - 0.05)
    return sorted(set(round(value, 3) for value in timestamps))


def _extract_frame(video: Path, timestamp: float, target: Path) -> None:
    ffmpeg = require_binary("ffmpeg")
    target.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(target),
        ]
    )


def score_frame(path: Path) -> tuple[float, list[str]]:
    reasons: list[str] = []
    with Image.open(path).convert("RGB") as image:
        stat = ImageStat.Stat(image.resize((128, 128)))
        brightness = sum(stat.mean) / 3
        variance = sum(stat.var) / 3
    if brightness < 12:
        reasons.append("near_black")
    if brightness > 245:
        reasons.append("overexposed")
    if variance < 20:
        reasons.append("low_detail")
    brightness_score = min(1.0, max(0.0, 1 - abs(brightness - 128) / 128))
    detail_score = min(1.0, variance / 1200)
    score = round((brightness_score * 0.45) + (detail_score * 0.55), 4)
    return score, reasons


def extract_interval_frames(
    video: Path,
    workspace: Path,
    *,
    duration_seconds: float,
    interval_seconds: int = 60,
) -> list[FrameArtifact]:
    output_dir = workspace / "frames" / "interval"
    artifacts: list[FrameArtifact] = []
    for index, timestamp in enumerate(interval_timestamps(duration_seconds, interval_seconds)):
        target = output_dir / f"interval-{index:04d}-{int(timestamp):06d}s.jpg"
        _extract_frame(video, timestamp, target)
        score, reasons = score_frame(target)
        artifacts.append(
            FrameArtifact(
                id=f"interval-{index:04d}",
                timestamp_seconds=timestamp,
                relative_path=str(target.relative_to(workspace)),
                kind="interval",
                preferred=not reasons,
                quality_score=score,
                rejection_reasons=reasons,
            )
        )
    return artifacts


def detect_scenes(video: Path, workspace: Path, threshold: float = 27.0) -> tuple[list[SceneArtifact], list[FrameArtifact]]:
    try:
        from scenedetect import AdaptiveDetector, SceneManager, open_video  # type: ignore
    except ImportError:
        return [], []
    scene_manager = SceneManager()
    scene_manager.add_detector(AdaptiveDetector(adaptive_threshold=threshold / 10))
    scene_manager.detect_scenes(open_video(str(video)))
    scene_list = scene_manager.get_scene_list()
    scenes: list[SceneArtifact] = []
    frames: list[FrameArtifact] = []
    output_dir = workspace / "frames" / "scenes"
    for index, (start, end) in enumerate(scene_list):
        start_seconds = start.get_seconds()
        end_seconds = end.get_seconds()
        midpoint = start_seconds + max(0.0, end_seconds - start_seconds) / 2
        target = output_dir / f"scene-{index:04d}-{int(midpoint):06d}s.jpg"
        _extract_frame(video, midpoint, target)
        score, reasons = score_frame(target)
        scenes.append(
            SceneArtifact(
                id=f"scene-{index:04d}",
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                keyframe_path=str(target.relative_to(workspace)),
                detector="pyscenedetect-adaptive",
                confidence=min(1.0, max(0.1, score)),
            )
        )
        frames.append(
            FrameArtifact(
                id=f"scene-frame-{index:04d}",
                timestamp_seconds=midpoint,
                relative_path=str(target.relative_to(workspace)),
                kind="scene",
                preferred=not reasons,
                quality_score=score,
                rejection_reasons=reasons,
            )
        )
    return scenes, frames


def make_contact_sheet(
    workspace: Path,
    frames: list[FrameArtifact],
    *,
    columns: int = 4,
    thumb_width: int = 320,
) -> Path:
    selected = [frame for frame in frames if frame.preferred] or frames
    if not selected:
        raise ValueError("No frames available for a contact sheet")
    images: list[tuple[Image.Image, FrameArtifact]] = []
    for artifact in selected:
        image = Image.open(workspace / artifact.relative_path).convert("RGB")
        scale = thumb_width / image.width
        images.append((image.resize((thumb_width, int(image.height * scale))), artifact))
    cell_height = max(image.height for image, _ in images) + 44
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (image, artifact) in enumerate(images):
        x = (index % columns) * thumb_width
        y = (index // columns) * cell_height
        sheet.paste(image, (x, y))
        label = f"{artifact.timestamp_seconds:0.1f}s | {artifact.kind} | {artifact.quality_score:0.2f}"
        draw.text((x + 8, y + image.height + 10), label, fill="black", font=font)
    target = workspace / "frames" / "contact_sheet.jpg"
    sheet.save(target, quality=90)
    for image, _ in images:
        image.close()
    return target


def save_frame_manifest(
    workspace: Path,
    frames: list[FrameArtifact],
    scenes: list[SceneArtifact],
) -> Path:
    target = workspace / "frames" / "frame_manifest.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "p66.frame_manifest.v1",
                "frames": [item.model_dump(mode="json") for item in frames],
                "scenes": [item.model_dump(mode="json") for item in scenes],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return target
