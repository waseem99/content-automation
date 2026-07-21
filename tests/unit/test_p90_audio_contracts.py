from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.audio.adapters import (
    AudioQualityPolicy,
    KokoroJobAdapter,
    KokoroParagraphContext,
    merge_pronunciation_rules,
    proportional_preview_timings,
    validate_forced_alignment,
)
from src.application.audio.models import (
    AlignmentSource,
    AudioTakeResult,
    MixTrackRequest,
    TrackRole,
)


def paragraph_context(**overrides):
    base = {
        "portfolio_content_id": uuid4(),
        "content_version": 1,
        "production_workflow_id": uuid4(),
        "production_workflow_version_id": uuid4(),
        "script_version_id": uuid4(),
        "audio_production_id": uuid4(),
        "paragraph_id": uuid4(),
        "paragraph_sequence": 1,
        "take_version": 1,
        "source_text": "Octopus arms process touch signals through distributed neural tissue.",
        "language": "en-US",
        "provider": "kokoro-onnx",
        "provider_voice_id": "af_heart",
        "approved_voice_id": uuid4(),
        "narration_preset_id": uuid4(),
        "speed": 0.98,
        "style": {"delivery": "warm and restrained"},
        "pronunciation_rules": {"octopus": "OK-tuh-pus"},
        "model_id": "kokoro-v1.0",
    }
    base.update(overrides)
    return KokoroParagraphContext(**base)


def test_kokoro_job_is_local_zero_fee_and_exact_version_bound() -> None:
    context = paragraph_context()
    request = KokoroJobAdapter().build_enqueue(context, actor="producer.one")

    assert request.job_type.value == "narration"
    assert request.provider == "kokoro-onnx"
    assert request.model_id == "kokoro-v1.0"
    assert request.estimated_cost_usd == 0
    assert request.reserved_cost_usd == 0
    assert request.input_payload["script_version_id"] == str(context.script_version_id)
    assert request.input_payload["audio_production_id"] == str(context.audio_production_id)
    assert request.input_payload["paragraph_id"] == str(context.paragraph_id)
    assert request.input_payload["billing"]["external_fee_allowed"] is False
    assert "take-1" in request.idempotency_key


def test_nonlocal_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="local Kokoro"):
        KokoroJobAdapter().build_enqueue(
            paragraph_context(provider="paid-cloud-tts"),
            actor="producer.one",
        )


def test_pronunciation_overrides_replace_preset_values_deterministically() -> None:
    merged = merge_pronunciation_rules(
        {"octopus": "old", "cephalopod": "SEF-uh-lo-pod"},
        [
            {"token": "octopus", "pronunciation": "OK-tuh-pus", "active": True},
            {"token": "ignored", "pronunciation": "old", "active": False},
        ],
    )
    assert merged == {
        "cephalopod": "SEF-uh-lo-pod",
        "octopus": "OK-tuh-pus",
    }


def test_forced_alignment_requires_exact_monotonic_word_sequence() -> None:
    text = "Octopus arms sense touch"
    timings = proportional_preview_timings(text, 4.0)
    validated = validate_forced_alignment(text=text, duration_seconds=4.0, timings=timings)
    assert [item.word for item in validated] == text.split()

    bad = [item.model_copy() for item in timings]
    bad[1] = bad[1].model_copy(update={"word": "wrong"})
    with pytest.raises(ValueError, match="word sequence"):
        validate_forced_alignment(text=text, duration_seconds=4.0, timings=bad)


def test_take_quality_fails_clipping_and_passes_clean_timed_audio() -> None:
    timings = proportional_preview_timings("clean timed audio", 3.0)
    clean = AudioTakeResult(
        asset_id=uuid4(),
        duration_seconds=3.0,
        sample_rate_hz=24000,
        channels=1,
        integrated_lufs=-16.2,
        true_peak_dbfs=-1.5,
        clipping_count=0,
        silence_ratio=0.05,
        timing_source=AlignmentSource.FORCED_ALIGNMENT,
        word_timings=timings,
    )
    status, evidence = AudioQualityPolicy().evaluate_take(clean)
    assert status == "pass"
    assert all(evidence["checks"].values())

    clipped = clean.model_copy(update={"clipping_count": 1})
    status, evidence = AudioQualityPolicy().evaluate_take(clipped)
    assert status == "fail"
    assert evidence["checks"]["no_clipping"] is False


def test_music_and_sfx_tracks_require_rights_ids() -> None:
    with pytest.raises(ValueError, match="asset_rights_id"):
        MixTrackRequest(track_role=TrackRole.MUSIC, asset_id=uuid4())
    narration = MixTrackRequest(track_role=TrackRole.NARRATION, asset_id=uuid4())
    assert narration.asset_rights_id is None
