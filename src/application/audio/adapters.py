from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from src.application.audio.models import AlignmentSource, AudioTakeResult, WordTiming
from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType


_WORD_RE = re.compile(r"\S+")


def canonical_fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def merge_pronunciation_rules(
    preset_rules: dict[str, Any] | None,
    overrides: Iterable[dict[str, Any]],
) -> dict[str, str]:
    merged = {
        str(token).strip(): str(pronunciation).strip()
        for token, pronunciation in dict(preset_rules or {}).items()
        if str(token).strip() and str(pronunciation).strip()
    }
    for item in overrides:
        if not item.get("active", True):
            continue
        token = str(item.get("token") or "").strip()
        pronunciation = str(item.get("pronunciation") or "").strip()
        if token and pronunciation:
            merged[token] = pronunciation
    return dict(sorted(merged.items(), key=lambda pair: pair[0].casefold()))


@dataclass(frozen=True, slots=True)
class KokoroParagraphContext:
    portfolio_content_id: UUID
    content_version: int
    production_workflow_id: UUID | None
    production_workflow_version_id: UUID | None
    script_version_id: UUID
    audio_production_id: UUID
    paragraph_id: UUID
    paragraph_sequence: int
    take_version: int
    source_text: str
    language: str
    provider: str
    provider_voice_id: str
    approved_voice_id: UUID
    narration_preset_id: UUID
    speed: float
    style: dict[str, Any]
    pronunciation_rules: dict[str, str]
    model_id: str


class KokoroJobAdapter:
    """Builds zero-fee, local-only narration jobs for the unified worker queue."""

    allowed_providers = frozenset({"kokoro", "kokoro-onnx"})

    def build_enqueue(
        self,
        context: KokoroParagraphContext,
        *,
        actor: str,
        preferred_worker_id: str | None = None,
        timeout_seconds: int = 300,
        max_attempts: int = 3,
    ) -> GenerationJobEnqueue:
        provider = context.provider.strip().lower()
        if provider not in self.allowed_providers:
            raise ValueError("Kokoro narration jobs require a local Kokoro provider")
        payload = {
            "script_version_id": str(context.script_version_id),
            "audio_production_id": str(context.audio_production_id),
            "paragraph_id": str(context.paragraph_id),
            "paragraph_sequence": context.paragraph_sequence,
            "take_version": context.take_version,
            "text": context.source_text,
            "language": context.language,
            "provider_voice_id": context.provider_voice_id,
            "approved_voice_id": str(context.approved_voice_id),
            "narration_preset_id": str(context.narration_preset_id),
            "speed": context.speed,
            "style": context.style,
            "pronunciation_rules": context.pronunciation_rules,
            "output_contract": {
                "format": "wav",
                "register_canonical_asset": True,
                "measure_loudness": True,
                "detect_clipping": True,
                "measure_silence": True,
                "forced_alignment_requested": True,
                "proportional_preview_fallback_allowed": True,
            },
            "billing": {
                "external_fee_allowed": False,
                "estimated_cost_usd": 0,
                "reserved_cost_usd": 0,
            },
            "requested_by": actor,
        }
        idempotency_key = (
            f"p90:narration:{context.audio_production_id}:"
            f"{context.paragraph_id}:take-{context.take_version}"
        )
        return GenerationJobEnqueue(
            portfolio_content_id=context.portfolio_content_id,
            content_version=context.content_version,
            production_workflow_id=context.production_workflow_id,
            production_workflow_version_id=context.production_workflow_version_id,
            job_type=GenerationJobType.NARRATION,
            provider=provider,
            model_id=context.model_id,
            preferred_worker_id=preferred_worker_id,
            idempotency_key=idempotency_key,
            input_payload=payload,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            estimated_cost_usd=Decimal("0"),
            reserved_cost_usd=Decimal("0"),
            legacy_source={"phase": "P90", "runtime": "local_kokoro"},
        )


@dataclass(frozen=True, slots=True)
class AudioQualityPolicy:
    target_lufs: float = -16.0
    loudness_tolerance_lu: float = 2.0
    peak_limit_dbfs: float = -1.0
    max_silence_ratio: float = 0.25

    def evaluate_take(self, result: AudioTakeResult) -> tuple[str, dict[str, Any]]:
        checks = {
            "loudness_within_tolerance": abs(result.integrated_lufs - self.target_lufs)
            <= self.loudness_tolerance_lu,
            "true_peak_within_limit": result.true_peak_dbfs <= self.peak_limit_dbfs,
            "no_clipping": result.clipping_count == 0,
            "silence_within_limit": result.silence_ratio <= self.max_silence_ratio,
            "timing_recorded": result.timing_source != AlignmentSource.NONE,
            "word_timings_present": bool(result.word_timings),
        }
        evidence = {
            "policy": {
                "target_lufs": self.target_lufs,
                "loudness_tolerance_lu": self.loudness_tolerance_lu,
                "peak_limit_dbfs": self.peak_limit_dbfs,
                "max_silence_ratio": self.max_silence_ratio,
            },
            "checks": checks,
            "measurements": {
                "integrated_lufs": result.integrated_lufs,
                "true_peak_dbfs": result.true_peak_dbfs,
                "clipping_count": result.clipping_count,
                "silence_ratio": result.silence_ratio,
                "duration_seconds": result.duration_seconds,
                "sample_rate_hz": result.sample_rate_hz,
                "channels": result.channels,
                "timing_source": result.timing_source.value,
            },
            **dict(result.qc_evidence),
        }
        return ("pass" if all(checks.values()) else "fail", evidence)


def proportional_preview_timings(text: str, duration_seconds: float) -> list[WordTiming]:
    """Preview-only timing fallback. It must never satisfy final audio approval."""

    words = _WORD_RE.findall(text)
    if not words or duration_seconds <= 0:
        return []
    step = duration_seconds / len(words)
    return [
        WordTiming(
            word=word,
            start_seconds=round(index * step, 4),
            end_seconds=round((index + 1) * step, 4),
        )
        for index, word in enumerate(words)
    ]


def validate_forced_alignment(
    *,
    text: str,
    duration_seconds: float,
    timings: Iterable[WordTiming | dict[str, Any]],
) -> list[WordTiming]:
    normalized = [item if isinstance(item, WordTiming) else WordTiming.model_validate(item) for item in timings]
    expected_words = _WORD_RE.findall(text)
    if not normalized:
        raise ValueError("forced alignment returned no word timings")
    if len(normalized) != len(expected_words):
        raise ValueError("forced alignment word count does not match paragraph text")
    previous_end = 0.0
    for expected, timing in zip(expected_words, normalized, strict=True):
        if timing.word.strip(".,!?;:\"'()[]{}").casefold() != expected.strip(".,!?;:\"'()[]{}").casefold():
            raise ValueError("forced alignment word sequence does not match paragraph text")
        if timing.start_seconds < previous_end or timing.end_seconds > duration_seconds + 0.05:
            raise ValueError("forced alignment timing range is invalid")
        previous_end = timing.end_seconds
    return normalized


def take_input_fingerprint(
    *,
    text: str,
    model_id: str,
    provider_voice_id: str,
    speed: float,
    style: dict[str, Any],
    pronunciation_rules: dict[str, str],
) -> str:
    return canonical_fingerprint(
        {
            "text": text,
            "model_id": model_id,
            "provider_voice_id": provider_voice_id,
            "speed": speed,
            "style": style,
            "pronunciation_rules": pronunciation_rules,
        }
    )
