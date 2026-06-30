"""Build real match context for script generation from manifest + clip audio."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.analyzer.transcriber import transcribe_audio
from src.config import Settings
from src.extractor.ffmpeg_clipper import extract_audio_wav, probe_duration


def _transcribe_media(media_path: Path, settings: Settings, max_duration: float | None = None) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        extract_audio_wav(media_path, wav_path, max_duration=max_duration)
        segments = transcribe_audio(
            wav_path,
            model_size=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip())


def build_match_context(
    manifest: dict,
    run_dir: Path,
    clip_files: list[str],
    settings: Settings,
) -> str:
    lines: list[str] = [
        f"Match topic: {manifest.get('topic', '')}",
    ]

    source_video = Path(manifest.get("source_video", ""))
    if source_video.exists():
        lines.append(f"Source video: {source_video.name}")
        try:
            duration = probe_duration(source_video)
            lines.append(f"Source duration: {duration:.1f}s")
            if duration <= 180:
                full_transcript = _transcribe_media(source_video, settings)
                if full_transcript:
                    lines.append(f"Full match commentary/audio: {full_transcript}")
        except OSError:
            pass

    clip_lookup = {clip["file"]: clip for clip in manifest.get("clips", [])}
    for clip_file in clip_files:
        meta = clip_lookup.get(clip_file, {})
        label = meta.get("label", "moment")
        start = meta.get("start", "?")
        end = meta.get("end", "?")
        commentary = (meta.get("source_text") or "").strip()

        clip_path = run_dir / clip_file
        if not commentary and clip_path.exists():
            commentary = _transcribe_media(clip_path, settings)

        lines.append(
            f"Selected clip {clip_file} [{start}-{end}] ({label}): "
            f"{commentary or 'crowd/no clear speech — describe tension from topic and teams'}"
        )

    return "\n".join(lines)
