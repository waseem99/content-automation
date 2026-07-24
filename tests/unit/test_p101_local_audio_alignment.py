from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.application.audio.models import AlignmentSource
from src.operations import local_audio_alignment_patch as alignment


def test_script_anchored_alignment_returns_exact_monotonic_script_words() -> None:
    result = alignment._interpolate_script_timings(
        text="One quick brown fox jumps",
        duration_seconds=2.5,
        recognized_words=[
            {"word": "One", "start": 0.05, "end": 0.30, "probability": 0.99},
            {"word": "quick", "start": 0.34, "end": 0.63, "probability": 0.98},
            {"word": "fox", "start": 1.10, "end": 1.38, "probability": 0.96},
            {"word": "jumps", "start": 1.45, "end": 1.85, "probability": 0.97},
        ],
        minimum_match_ratio=0.72,
    )

    assert result.source is AlignmentSource.FORCED_ALIGNMENT
    assert [item.word for item in result.word_timings] == [
        "One",
        "quick",
        "brown",
        "fox",
        "jumps",
    ]
    assert result.evidence["matched_script_words"] == 4
    assert result.evidence["transcript_coverage"] == 0.8
    assert all(
        current.end_seconds <= following.start_seconds
        for current, following in zip(result.word_timings, result.word_timings[1:])
    )
    assert result.word_timings[-1].end_seconds <= 2.5


def test_script_anchored_alignment_rejects_low_transcript_coverage() -> None:
    with pytest.raises(ValueError, match="transcript coverage"):
        alignment._interpolate_script_timings(
            text="One quick brown fox jumps over the fence",
            duration_seconds=3.0,
            recognized_words=[
                {"word": "One", "start": 0.0, "end": 0.2, "probability": 0.99},
                {"word": "fence", "start": 2.5, "end": 2.9, "probability": 0.95},
            ],
            minimum_match_ratio=0.72,
        )


def test_narration_alignment_failure_remains_preview_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "narration.wav"
    audio_path.write_bytes(b"RIFF-preview")
    monkeypatch.setattr(
        alignment,
        "_ORIGINAL_NARRATION",
        lambda _worker, _job: {
            "storage_path": str(audio_path),
            "text": "One quick brown fox",
            "metrics": {"duration_seconds": 2.0},
        },
    )
    monkeypatch.setattr(
        alignment,
        "align_local_audio",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("model unavailable")),
    )

    output = alignment._narration_with_alignment(
        SimpleNamespace(),
        {"input_payload": {"language": "en-US"}},
    )

    assert output["timing_source"] == AlignmentSource.PROPORTIONAL_PREVIEW.value
    assert output["word_timings"]
    assert output["alignment_evidence"]["final_approval_allowed"] is False
    assert output["alignment_evidence"]["external_fee_incurred"] is False
    assert "model unavailable" in output["alignment_evidence"]["failure"]


def test_alignment_model_dependency_is_lazy() -> None:
    source = Path(alignment.__file__).read_text(encoding="utf-8")
    assert "from faster_whisper import WhisperModel" in source
    assert source.index("def _load_model") < source.index("from faster_whisper import WhisperModel")
