from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

from src.application.audio.adapters import proportional_preview_timings, validate_forced_alignment
from src.application.audio.models import AlignmentSource, AudioTakeResult, WordTiming
from src.operations.local_worker import LocalGenerationWorker


_WORD_RE = re.compile(r"\S+")
_MODEL_CACHE: dict[tuple[str, str, str], Any] = {}
_MODEL_LOCK = Lock()
_ORIGINAL_NARRATION = LocalGenerationWorker._narration
_PATCHED = False


def _normalized_word(value: str) -> str:
    return re.sub(r"[^\w']+", "", value, flags=re.UNICODE).casefold()


@dataclass(frozen=True, slots=True)
class AlignmentEvidence:
    source: AlignmentSource
    word_timings: list[WordTiming]
    evidence: dict[str, Any]


def _interpolate_script_timings(
    *,
    text: str,
    duration_seconds: float,
    recognized_words: Iterable[dict[str, Any]],
    minimum_match_ratio: float,
) -> AlignmentEvidence:
    expected = _WORD_RE.findall(text)
    recognized = [
        {
            "word": str(item.get("word") or "").strip(),
            "start": float(item.get("start") or 0),
            "end": float(item.get("end") or 0),
            "probability": float(item.get("probability") or 0),
        }
        for item in recognized_words
        if str(item.get("word") or "").strip()
        and item.get("start") is not None
        and item.get("end") is not None
        and float(item.get("end") or 0) > float(item.get("start") or 0)
    ]
    if not expected or not recognized or duration_seconds <= 0:
        raise ValueError("alignment requires script words, recognized words, and duration")

    expected_tokens = [_normalized_word(word) for word in expected]
    recognized_tokens = [_normalized_word(item["word"]) for item in recognized]
    matcher = difflib.SequenceMatcher(
        None,
        expected_tokens,
        recognized_tokens,
        autojunk=False,
    )
    blocks = [block for block in matcher.get_matching_blocks() if block.size]
    matched = sum(block.size for block in blocks)
    ratio = matched / max(len(expected_tokens), 1)
    if ratio < minimum_match_ratio:
        raise ValueError(
            f"alignment transcript coverage {ratio:.3f} is below {minimum_match_ratio:.3f}"
        )

    anchors: dict[int, tuple[float, float, float]] = {}
    for block in blocks:
        for offset in range(block.size):
            expected_index = block.a + offset
            recognized_item = recognized[block.b + offset]
            anchors[expected_index] = (
                max(0.0, recognized_item["start"]),
                min(duration_seconds, recognized_item["end"]),
                recognized_item["probability"],
            )

    boundaries = sorted(anchors)
    timings: list[WordTiming | None] = [None] * len(expected)
    for index, (start, end, _probability) in anchors.items():
        if end <= start:
            end = min(duration_seconds, start + 0.02)
        timings[index] = WordTiming(
            word=expected[index],
            start_seconds=round(start, 4),
            end_seconds=round(end, 4),
        )

    segments: list[tuple[int, int, float, float]] = []
    first_anchor = boundaries[0]
    if first_anchor > 0:
        segments.append((0, first_anchor, 0.0, anchors[first_anchor][0]))
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        if right - left > 1:
            segments.append((left + 1, right, anchors[left][1], anchors[right][0]))
    last_anchor = boundaries[-1]
    if last_anchor < len(expected) - 1:
        segments.append((last_anchor + 1, len(expected), anchors[last_anchor][1], duration_seconds))

    for start_index, end_index, window_start, window_end in segments:
        count = end_index - start_index
        safe_start = max(0.0, min(window_start, duration_seconds))
        safe_end = max(safe_start + (0.02 * count), min(window_end, duration_seconds))
        if safe_end > duration_seconds:
            safe_end = duration_seconds
            safe_start = max(0.0, safe_end - (0.02 * count))
        step = max((safe_end - safe_start) / max(count, 1), 0.02)
        for offset, index in enumerate(range(start_index, end_index)):
            word_start = min(duration_seconds, safe_start + (offset * step))
            word_end = min(duration_seconds, safe_start + ((offset + 1) * step))
            timings[index] = WordTiming(
                word=expected[index],
                start_seconds=round(word_start, 4),
                end_seconds=round(max(word_end, word_start + 0.001), 4),
            )

    resolved = [item for item in timings if item is not None]
    # Clamp overlaps from noisy ASR anchors while retaining the measured anchor order.
    monotonic: list[WordTiming] = []
    previous_end = 0.0
    for index, item in enumerate(resolved):
        start = max(previous_end, min(item.start_seconds, duration_seconds))
        remaining = len(resolved) - index
        latest_end = duration_seconds - max(0, remaining - 1) * 0.001
        end = min(latest_end, max(start + 0.001, item.end_seconds))
        monotonic.append(
            WordTiming(
                word=item.word,
                start_seconds=round(start, 4),
                end_seconds=round(end, 4),
            )
        )
        previous_end = end

    validated = validate_forced_alignment(
        text=text,
        duration_seconds=duration_seconds,
        timings=monotonic,
    )
    probabilities = [value[2] for value in anchors.values()]
    return AlignmentEvidence(
        source=AlignmentSource.FORCED_ALIGNMENT,
        word_timings=validated,
        evidence={
            "alignment_engine": "faster-whisper-script-anchored",
            "matched_script_words": matched,
            "script_word_count": len(expected),
            "recognized_word_count": len(recognized),
            "transcript_coverage": round(ratio, 4),
            "mean_anchor_probability": round(
                sum(probabilities) / max(len(probabilities), 1),
                4,
            ),
            "validation": "exact_script_sequence_and_monotonic_range",
        },
    )


def _load_model() -> Any:
    model_id = os.getenv("LOCAL_ALIGNMENT_MODEL_ID", "tiny").strip() or "tiny"
    device = os.getenv("LOCAL_ALIGNMENT_DEVICE", "cpu").strip() or "cpu"
    compute_type = os.getenv("LOCAL_ALIGNMENT_COMPUTE_TYPE", "int8").strip() or "int8"
    key = (model_id, device, compute_type)
    with _MODEL_LOCK:
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        from faster_whisper import WhisperModel

        model = WhisperModel(model_id, device=device, compute_type=compute_type)
        _MODEL_CACHE[key] = model
        return model


def align_local_audio(
    *,
    path: Path,
    text: str,
    language: str,
    duration_seconds: float,
) -> AlignmentEvidence:
    enabled = os.getenv("LOCAL_ALIGNMENT_ENABLED", "true").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        raise RuntimeError("local alignment is disabled")
    model = _load_model()
    language_code = language.split("-", 1)[0].strip().lower() or None
    segments, info = model.transcribe(
        str(path),
        language=language_code,
        beam_size=1,
        word_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    recognized: list[dict[str, Any]] = []
    for segment in segments:
        for word in segment.words or []:
            recognized.append(
                {
                    "word": word.word,
                    "start": word.start,
                    "end": word.end,
                    "probability": word.probability,
                }
            )
    minimum = float(os.getenv("LOCAL_ALIGNMENT_MINIMUM_COVERAGE", "0.72"))
    result = _interpolate_script_timings(
        text=text,
        duration_seconds=duration_seconds,
        recognized_words=recognized,
        minimum_match_ratio=max(0.5, min(minimum, 1.0)),
    )
    return AlignmentEvidence(
        source=result.source,
        word_timings=result.word_timings,
        evidence={
            **result.evidence,
            "detected_language": getattr(info, "language", language_code),
            "detected_language_probability": getattr(
                info,
                "language_probability",
                None,
            ),
            "model_id": os.getenv("LOCAL_ALIGNMENT_MODEL_ID", "tiny"),
            "device": os.getenv("LOCAL_ALIGNMENT_DEVICE", "cpu"),
            "external_fee_incurred": False,
        },
    )


def _narration_with_alignment(
    self: LocalGenerationWorker,
    job: dict[str, Any],
) -> dict[str, Any]:
    output = _ORIGINAL_NARRATION(self, job)
    payload = dict(job["input_payload"])
    try:
        aligned = align_local_audio(
            path=Path(output["storage_path"]),
            text=str(output["text"]),
            language=str(payload.get("language") or "en-US"),
            duration_seconds=float(output["metrics"]["duration_seconds"]),
        )
        output["timing_source"] = aligned.source.value
        output["word_timings"] = [
            item.model_dump(mode="json") for item in aligned.word_timings
        ]
        output["alignment_evidence"] = aligned.evidence
    except Exception as exc:
        preview = proportional_preview_timings(
            output["text"],
            output["metrics"]["duration_seconds"],
        )
        output["timing_source"] = AlignmentSource.PROPORTIONAL_PREVIEW.value
        output["word_timings"] = [item.model_dump(mode="json") for item in preview]
        output["alignment_evidence"] = {
            "alignment_engine": "proportional_preview_fallback",
            "failure": f"{type(exc).__name__}: {exc}"[:1000],
            "final_approval_allowed": False,
            "external_fee_incurred": False,
        }
    return output


def _register_audio_with_alignment(
    self: LocalGenerationWorker,
    *,
    job: dict[str, Any],
    output: dict[str, Any],
) -> None:
    asset_id = self._asset(job=job, output=output, asset_type="audio")
    with self.database.connection() as conn:
        take = conn.execute(
            "SELECT id FROM football_brief.audio_segment_takes WHERE generation_job_id=%s",
            (job["id"],),
        ).fetchone()
    if not take:
        raise RuntimeError("audio take binding not found")
    metrics = output["metrics"]
    source = AlignmentSource(
        output.get("timing_source")
        or AlignmentSource.PROPORTIONAL_PREVIEW.value
    )
    timings = [
        item if isinstance(item, WordTiming) else WordTiming.model_validate(item)
        for item in output.get("word_timings") or []
    ]
    if not timings:
        timings = proportional_preview_timings(
            output["text"],
            metrics["duration_seconds"],
        )
        source = AlignmentSource.PROPORTIONAL_PREVIEW
    self.audio.register_take_result(
        take_id=take["id"],
        result=AudioTakeResult(
            asset_id=asset_id,
            duration_seconds=metrics["duration_seconds"],
            sample_rate_hz=metrics["sample_rate_hz"],
            channels=metrics["channels"],
            integrated_lufs=metrics["integrated_lufs"],
            true_peak_dbfs=metrics["true_peak_dbfs"],
            clipping_count=metrics["clipping_count"],
            silence_ratio=metrics["silence_ratio"],
            timing_source=source,
            word_timings=timings,
            qc_evidence={
                "measurement_method": "local_preview_rms_approximation",
                "alignment": output.get("alignment_evidence") or {},
                "forced_alignment_required_for_final_approval": True,
                "forced_alignment_satisfied": source
                == AlignmentSource.FORCED_ALIGNMENT,
            },
        ),
        actor=self.worker_id,
    )


def apply_local_audio_alignment_patch() -> None:
    global _PATCHED
    if _PATCHED:
        return
    LocalGenerationWorker._narration = _narration_with_alignment  # type: ignore[method-assign]
    LocalGenerationWorker._register_audio = _register_audio_with_alignment  # type: ignore[method-assign]
    _PATCHED = True


__all__ = [
    "AlignmentEvidence",
    "align_local_audio",
    "apply_local_audio_alignment_patch",
    "_interpolate_script_timings",
]
