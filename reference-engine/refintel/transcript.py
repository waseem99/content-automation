from __future__ import annotations

import json
import math
from pathlib import Path

from .models import TranscriptSegment, TranscriptWord


def _format_srt_time(seconds: float, separator: str = ",") -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}{separator}{millis:03d}"


def write_transcript_outputs(
    workspace: Path,
    segments: list[TranscriptSegment],
    *,
    language: str | None,
    provider: str,
    provider_version: str,
) -> dict[str, Path]:
    output_dir = workspace / "transcript"
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_path = output_dir / "transcript.txt"
    json_path = output_dir / "transcript.json"
    srt_path = output_dir / "captions.srt"
    vtt_path = output_dir / "captions.vtt"
    words_path = output_dir / "word_timestamps.json"

    txt_path.write_text("\n".join(segment.text for segment in segments), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "schema_version": "p66.transcript.v1",
                "language": language,
                "provider": provider,
                "provider_version": provider_version,
                "segments": [segment.model_dump(mode="json") for segment in segments],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    words_path.write_text(
        json.dumps(
            [
                word.model_dump(mode="json")
                for segment in segments
                for word in segment.words
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    srt_blocks: list[str] = []
    vtt_blocks = ["WEBVTT", ""]
    for index, segment in enumerate(segments, start=1):
        srt_blocks.append(
            f"{index}\n{_format_srt_time(segment.start_seconds)} --> "
            f"{_format_srt_time(segment.end_seconds)}\n{segment.text}\n"
        )
        vtt_blocks.append(
            f"{_format_srt_time(segment.start_seconds, '.')} --> "
            f"{_format_srt_time(segment.end_seconds, '.')}\n{segment.text}\n"
        )
    srt_path.write_text("\n".join(srt_blocks), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_blocks), encoding="utf-8")
    return {
        "txt": txt_path,
        "json": json_path,
        "srt": srt_path,
        "vtt": vtt_path,
        "words": words_path,
    }


def transcribe_audio(
    audio_path: Path,
    workspace: Path,
    *,
    model_size: str = "small",
    device: str = "auto",
    compute_type: str = "default",
    language: str | None = None,
) -> tuple[list[TranscriptSegment], dict[str, object]]:
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        segments: list[TranscriptSegment] = []
        write_transcript_outputs(
            workspace,
            segments,
            language=language,
            provider="no-audio-fallback",
            provider_version="1",
        )
        return segments, {"provider": "no-audio-fallback", "language": language}
    try:
        from faster_whisper import WhisperModel  # type: ignore
        import faster_whisper  # type: ignore
    except ImportError:
        segments = []
        write_transcript_outputs(
            workspace,
            segments,
            language=language,
            provider="not-installed-fallback",
            provider_version="1",
        )
        return segments, {
            "provider": "not-installed-fallback",
            "language": language,
            "warning": "Install the speech extra to enable local transcription.",
        }

    resolved_device = device
    if resolved_device == "auto":
        resolved_device = "cuda" if _cuda_available() else "cpu"
    resolved_compute = _resolve_compute_type(resolved_device, compute_type)
    try:
        model = WhisperModel(
            model_size,
            device=resolved_device,
            compute_type=resolved_compute,
        )
    except ValueError as exc:
        # Some Windows systems expose a CUDA device even though its backend cannot
        # execute float16 efficiently. A default request must remain portable.
        if compute_type != "default" or "float16" not in str(exc).lower():
            raise
        resolved_compute = "int8" if resolved_device == "cpu" else "float32"
        model = WhisperModel(
            model_size,
            device=resolved_device,
            compute_type=resolved_compute,
        )
    raw_segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        word_timestamps=True,
        beam_size=5,
    )
    segments: list[TranscriptSegment] = []
    for index, raw in enumerate(raw_segments):
        words = [
            TranscriptWord(
                text=word.word.strip(),
                start_seconds=float(word.start or raw.start),
                end_seconds=float(word.end or raw.end),
                confidence=(float(word.probability) if word.probability is not None else None),
            )
            for word in (raw.words or [])
            if word.word.strip()
        ]
        text = raw.text.strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                id=f"segment-{index:05d}",
                start_seconds=float(raw.start),
                end_seconds=float(raw.end),
                text=text,
                words=words,
            )
        )
    detected_language = getattr(info, "language", None) or language
    version = getattr(faster_whisper, "__version__", "unknown")
    write_transcript_outputs(
        workspace,
        segments,
        language=detected_language,
        provider="faster-whisper",
        provider_version=version,
    )
    return segments, {
        "provider": "faster-whisper",
        "provider_version": version,
        "model": model_size,
        "device": resolved_device,
        "compute_type": resolved_compute,
        "language": detected_language,
        "language_probability": getattr(info, "language_probability", None),
    }


def _cuda_available() -> bool:
    try:
        import ctranslate2  # type: ignore

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _resolve_compute_type(device: str, requested: str) -> str:
    if requested != "default":
        return requested
    preferences = (
        ("float16", "int8_float16", "int8_float32", "int8", "float32")
        if device == "cuda"
        else ("int8", "int8_float32", "float32")
    )
    try:
        import ctranslate2  # type: ignore

        supported = set(ctranslate2.get_supported_compute_types(device))
        return next(item for item in preferences if item in supported)
    except (ImportError, RuntimeError, StopIteration, TypeError, ValueError):
        return "float16" if device == "cuda" else "int8"


def analyze_transcript(
    segments: list[TranscriptSegment],
    *,
    duration_seconds: float,
) -> dict[str, object]:
    words = [word for segment in segments for word in segment.words]
    if not words:
        word_count = sum(len(segment.text.split()) for segment in segments)
    else:
        word_count = len(words)
    minutes = max(duration_seconds / 60, 1 / 60)
    speech_seconds = sum(
        max(0.0, segment.end_seconds - segment.start_seconds) for segment in segments
    )
    first_spoken = segments[0].start_seconds if segments else None
    questions = sum(segment.text.count("?") for segment in segments)
    cta_terms = (
        "follow",
        "subscribe",
        "comment",
        "share",
        "watch",
        "learn more",
        "visit",
        "click",
    )
    cta_candidates = [
        segment.model_dump(mode="json")
        for segment in segments
        if any(term in segment.text.lower() for term in cta_terms)
    ]
    phrase_word_counts = [len(segment.text.split()) for segment in segments if segment.text]
    average_phrase_words = (
        round(sum(phrase_word_counts) / len(phrase_word_counts), 2)
        if phrase_word_counts
        else 0
    )
    return {
        "word_count": word_count,
        "words_per_minute": round(word_count / minutes, 2),
        "speech_seconds": round(speech_seconds, 3),
        "speech_density": round(min(1.0, speech_seconds / max(duration_seconds, 0.001)), 4),
        "silence_percentage": round(
            max(0.0, 1 - speech_seconds / max(duration_seconds, 0.001)) * 100, 2
        ),
        "first_spoken_line_seconds": first_spoken,
        "question_count": questions,
        "average_caption_phrase_words": average_phrase_words,
        "caption_phrase_count": len(segments),
        "cta_candidates": cta_candidates,
    }
