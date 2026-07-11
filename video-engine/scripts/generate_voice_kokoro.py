from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def retime_project(project: dict, target_duration: float) -> dict:
    source_duration = float(project["render"]["durationSeconds"])
    if source_duration <= 0:
        raise ValueError("Project duration must be positive")
    scale = target_duration / source_duration
    updated = json.loads(json.dumps(project))
    for scene in updated["scenes"]:
        scene["startSec"] = round(float(scene["startSec"]) * scale, 3)
        scene["endSec"] = round(float(scene["endSec"]) * scale, 3)
    for caption in updated["captions"]:
        caption["startSec"] = round(float(caption["startSec"]) * scale, 3)
        caption["endSec"] = round(float(caption["endSec"]) * scale, 3)
    updated["render"]["durationSeconds"] = round(target_duration, 3)
    return updated


def approximate_alignment(text: str, duration: float) -> list[dict[str, float | str]]:
    words = [word for word in text.split() if word]
    if not words:
        return []
    weights = [max(1, len(word.strip(".,!?;:\"'()[]{}"))) for word in words]
    total = sum(weights)
    cursor = 0.0
    alignment: list[dict[str, float | str]] = []
    for word, weight in zip(words, weights, strict=True):
        span = duration * weight / total
        alignment.append(
            {
                "word": word,
                "startSec": round(cursor, 4),
                "endSec": round(cursor + span, 4),
                "timingBasis": "proportional_estimate",
            }
        )
        cursor += span
    alignment[-1]["endSec"] = round(duration, 4)
    return alignment


def synthesize(project_path: Path, voice: str, speed: float) -> tuple[Path, Path, Path]:
    try:
        from kokoro import KPipeline
    except ImportError as exc:
        raise RuntimeError(
            "Kokoro is not installed. Run: pip install -r voice-requirements.txt"
        ) from exc

    root = Path.cwd()
    project = json.loads(project_path.read_text(encoding="utf-8"))
    out_dir = root / "out"
    public_dir = root / "public" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)

    pipeline = KPipeline(lang_code=os.getenv("KOKORO_LANG_CODE", "a"))
    chunks: list[np.ndarray] = []
    sample_rate = 24000
    silence = np.zeros(int(sample_rate * 0.055), dtype=np.float32)
    for _, _, audio in pipeline(project["narration"], voice=voice, speed=speed):
        chunk = np.asarray(audio, dtype=np.float32)
        if chunk.size:
            chunks.append(chunk)
            chunks.append(silence)
    if not chunks:
        raise RuntimeError("Kokoro returned no audio")
    waveform = np.concatenate(chunks)
    peak = float(np.max(np.abs(waveform))) if waveform.size else 0.0
    if peak > 0.98:
        waveform = waveform * (0.98 / peak)

    audio_name = f"{project['id']}-kokoro.wav"
    audio_path = public_dir / audio_name
    sf.write(audio_path, waveform, sample_rate, subtype="PCM_16")
    audio_duration = len(waveform) / sample_rate
    target_duration = max(3.0, audio_duration + 0.35)
    voiced_project = retime_project(project, target_duration)
    voiced_project["voiceoverFile"] = f"generated/{audio_name}"
    voiced_project["voiceGeneration"] = {
        "provider": "kokoro",
        "model": "hexgrad/Kokoro-82M",
        "voice": voice,
        "speed": speed,
        "sampleRate": sample_rate,
        "audioDurationSeconds": round(audio_duration, 4),
        "timingBasis": "project_timeline_scaled_to_audio_duration",
        "costModel": "local_no_per_character_fee",
    }

    alignment_path = out_dir / f"{project['id']}-kokoro-alignment.json"
    alignment_path.write_text(
        json.dumps(
            {
                "provider": "kokoro",
                "model": "hexgrad/Kokoro-82M",
                "voice": voice,
                "durationSeconds": round(audio_duration, 4),
                "alignment": approximate_alignment(project["narration"], audio_duration),
                "warning": "Word timings are proportional estimates, not forced alignment.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    voiced_project["voiceGeneration"]["alignmentFile"] = str(
        alignment_path.relative_to(root)
    )

    voiced_path = out_dir / f"{project['id']}-kokoro-voiced.json"
    voiced_path.write_text(json.dumps(voiced_project, indent=2), encoding="utf-8")
    return audio_path, alignment_path, voiced_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--voice", default=os.getenv("KOKORO_VOICE", "af_heart"))
    parser.add_argument("--speed", type=float, default=float(os.getenv("KOKORO_SPEED", "1.08")))
    args = parser.parse_args()
    try:
        audio, alignment, voiced = synthesize(args.project.resolve(), args.voice, args.speed)
    except Exception as exc:  # noqa: BLE001
        print(f"Kokoro generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Voiceover written to {audio}")
    print(f"Alignment written to {alignment}")
    print(f"Render project written to {voiced}")


if __name__ == "__main__":
    main()
