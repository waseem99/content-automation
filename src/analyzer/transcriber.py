"""Speech transcription with faster-whisper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


def transcribe_audio(
    wav_path: Path,
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
) -> list[TranscriptSegment]:
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(str(wav_path), vad_filter=True)

    results: list[TranscriptSegment] = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        results.append(
            TranscriptSegment(
                start=float(segment.start),
                end=float(segment.end),
                text=text,
            )
        )
    return results
