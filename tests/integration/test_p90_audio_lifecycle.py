from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from src.application.audio.adapters import proportional_preview_timings
from src.application.audio.models import (
    AlignmentSource,
    AssemblyEnqueueRequest,
    AudioDecision,
    AudioInitializeRequest,
    AudioReviewActionType,
    AudioTakeResult,
    MixRegistrationRequest,
    MixRevisionRequest,
    MixTrackRequest,
    ReviewActionRequest,
    TrackRole,
)
from src.application.audio.service import AudioProductionError, AudioProductionService
from src.application.brand_profile_service import BrandProfileService
from tests.integration.p90_audio_support import (
    complete_next_narration_job,
    p89_database,
    p89_seeded,
    p90_ready,
    register_audio_asset,
)


pytestmark = pytest.mark.integration


def initialize_and_select_takes(database, ready, *, timing_source: AlignmentSource):
    service = AudioProductionService(database)
    initialized = service.initialize(
        content_id=ready["content_one"],
        request=AudioInitializeRequest(model_id="kokoro-v1.0"),
        actor=ready["producer"],
    )
    production_id = initialized["production"]["id"]
    assert initialized["created"] is True
    assert len(initialized["paragraphs"]) == len(initialized["takes"])
    assert all(take["status"] == "queued" for take in initialized["takes"])

    paragraph_duration = 60 / len(initialized["paragraphs"])
    for index in range(len(initialized["paragraphs"])):
        job = complete_next_narration_job(
            database,
            worker=ready["producer"],
            brand_id=ready["brand_one"],
        )
        detail = service.detail(production_id=production_id)
        take = next(row for row in detail["takes"] if str(row["generation_job_id"]) == str(job["id"]))
        paragraph = next(row for row in detail["paragraphs"] if str(row["id"]) == str(take["paragraph_id"]))
        asset_id = register_audio_asset(
            database,
            key=f"segment-{production_id}-{index}-take-{take['take_version']}",
            created_by=ready["producer"],
        )
        timings = proportional_preview_timings(paragraph["source_text"], paragraph_duration)
        service.register_take_result(
            take_id=take["id"],
            result=AudioTakeResult(
                asset_id=asset_id,
                duration_seconds=paragraph_duration,
                sample_rate_hz=24000,
                channels=1,
                integrated_lufs=-16.1,
                true_peak_dbfs=-1.5,
                clipping_count=0,
                silence_ratio=0.05,
                timing_source=timing_source,
                word_timings=timings,
                qc_evidence={"local_worker": True, "external_fee_incurred": False},
            ),
            actor=ready["producer"],
        )
        current = service.detail(production_id=production_id)
        service.select_take(
            production_id=production_id,
            take_id=take["id"],
            expected_lock_version=current["production"]["lock_version"],
            actor=ready["producer"],
        )
    return service, service.detail(production_id=production_id)


def register_clean_mix(database, ready, service, detail, *, alignment_source: AlignmentSource):
    production_id = detail["production"]["id"]
    narration_asset = register_audio_asset(
        database,
        key=f"narration-{production_id}-{detail['production']['current_mix_version']}",
        created_by=ready["producer"],
    )
    final_asset = register_audio_asset(
        database,
        key=f"final-{production_id}-{detail['production']['current_mix_version']}",
        created_by=ready["producer"],
    )
    return service.register_mix(
        production_id=production_id,
        request=MixRegistrationRequest(
            expected_lock_version=detail["production"]["lock_version"],
            narration_asset_id=narration_asset,
            final_mix_asset_id=final_asset,
            target_lufs=-16.0,
            peak_limit_dbfs=-1.0,
            measured_lufs=-16.1,
            true_peak_dbfs=-1.5,
            clipping_count=0,
            silence_ratio=0.05,
            duration_seconds=60,
            waveform_metadata={"peaks": [0.1, 0.3, 0.2], "sample_rate_hz": 24000},
            segment_snapshot=[{"validated_by_service": True}],
            mix_settings={"normalization": "ebu-r128", "local": True},
            alignment_source=alignment_source,
            tracks=[
                MixTrackRequest(
                    track_role=TrackRole.NARRATION,
                    asset_id=narration_asset,
                    level_db=0,
                )
            ],
        ),
        actor=ready["producer"],
    )


def test_unapproved_script_cannot_start_audio(p89_database, p89_seeded) -> None:
    with p89_database.connection() as conn:
        preset = conn.execute(
            """SELECT id FROM football_brief.brand_narration_presets
               WHERE brand_profile_id=%s AND is_default=true""",
            (p89_seeded["profile_two"],),
        ).fetchone()
    assert BrandProfileService(p89_database).bind_content(
        content_id=p89_seeded["content_two"], preset_id=preset["id"]
    )["ok"] is True

    with pytest.raises(AudioProductionError, match="approved_script"):
        AudioProductionService(p89_database).initialize(
            content_id=p89_seeded["content_two"],
            request=AudioInitializeRequest(),
            actor=p89_seeded["outsider"],
        )


def test_paragraph_regeneration_quality_review_and_assembly_gate(p89_database, p90_ready) -> None:
    service, detail = initialize_and_select_takes(
        p89_database, p90_ready, timing_source=AlignmentSource.FORCED_ALIGNMENT
    )
    production_id = detail["production"]["id"]
    selected_before = {
        str(take["paragraph_id"]): str(take["id"])
        for take in detail["takes"]
        if take["status"] == "selected"
    }
    target_paragraph = detail["paragraphs"][1]

    regenerated = service.regenerate_paragraph(
        production_id=production_id,
        paragraph_id=target_paragraph["id"],
        request=AudioInitializeRequest(model_id="kokoro-v1.0"),
        actor=p90_ready["producer"],
    )
    assert regenerated["enqueued_take"]["take_version"] == 2
    queued_for_target = [
        take for take in regenerated["takes"]
        if str(take["paragraph_id"]) == str(target_paragraph["id"])
    ]
    assert len(queued_for_target) == 2
    assert sum(take["status"] == "queued" for take in queued_for_target) == 1

    job = complete_next_narration_job(
        p89_database,
        worker=p90_ready["producer"],
        brand_id=p90_ready["brand_one"],
    )
    refreshed = service.detail(production_id=production_id)
    new_take = next(take for take in refreshed["takes"] if str(take["generation_job_id"]) == str(job["id"]))
    asset_id = register_audio_asset(
        p89_database,
        key=f"regenerated-{new_take['id']}",
        created_by=p90_ready["producer"],
    )
    timings = proportional_preview_timings(target_paragraph["source_text"], 20)
    service.register_take_result(
        take_id=new_take["id"],
        result=AudioTakeResult(
            asset_id=asset_id,
            duration_seconds=20,
            sample_rate_hz=24000,
            channels=1,
            integrated_lufs=-16,
            true_peak_dbfs=-1.4,
            clipping_count=0,
            silence_ratio=0.04,
            timing_source=AlignmentSource.FORCED_ALIGNMENT,
            word_timings=timings,
        ),
        actor=p90_ready["producer"],
    )
    current = service.detail(production_id=production_id)
    selected = service.select_take(
        production_id=production_id,
        take_id=new_take["id"],
        expected_lock_version=current["production"]["lock_version"],
        actor=p90_ready["producer"],
    )
    selected_after = {
        str(take["paragraph_id"]): str(take["id"])
        for take in selected["takes"]
        if take["status"] == "selected"
    }
    assert selected_after[str(target_paragraph["id"])] == str(new_take["id"])
    for paragraph_id, take_id in selected_before.items():
        if paragraph_id != str(target_paragraph["id"]):
            assert selected_after[paragraph_id] == take_id

    with pytest.raises(AudioProductionError, match="approved_audio_mix_required"):
        service.enqueue_assembly(
            production_id=production_id,
            request=AssemblyEnqueueRequest(
                expected_lock_version=selected["production"]["lock_version"]
            ),
            actor=p90_ready["producer"],
        )

    invalid_music = register_audio_asset(
        p89_database,
        key=f"unlicensed-music-{production_id}",
        created_by=p90_ready["producer"],
    )
    with p89_database.transaction() as conn:
        pending_rights = conn.execute(
            """INSERT INTO football_brief.asset_rights
               (asset_id, rights_basis, commercial_use_allowed,
                modification_allowed, approval_status)
               VALUES (%s,'licensed',true,true,'pending') RETURNING id""",
            (invalid_music,),
        ).fetchone()
    narration_asset = register_audio_asset(
        p89_database,
        key=f"rights-test-narration-{production_id}",
        created_by=p90_ready["producer"],
    )
    final_asset = register_audio_asset(
        p89_database,
        key=f"rights-test-final-{production_id}",
        created_by=p90_ready["producer"],
    )
    with pytest.raises(psycopg.Error, match="approved, evidenced"):
        service.register_mix(
            production_id=production_id,
            request=MixRegistrationRequest(
                expected_lock_version=selected["production"]["lock_version"],
                narration_asset_id=narration_asset,
                final_mix_asset_id=final_asset,
                measured_lufs=-16,
                true_peak_dbfs=-1.5,
                clipping_count=0,
                silence_ratio=0.05,
                duration_seconds=60,
                waveform_metadata={"peaks": [0.1]},
                segment_snapshot=[{"placeholder": True}],
                alignment_source=AlignmentSource.FORCED_ALIGNMENT,
                tracks=[
                    MixTrackRequest(track_role=TrackRole.NARRATION, asset_id=narration_asset),
                    MixTrackRequest(
                        track_role=TrackRole.MUSIC,
                        asset_id=invalid_music,
                        asset_rights_id=pending_rights["id"],
                        level_db=-24,
                        ducking_db=-8,
                    ),
                ],
            ),
            actor=p90_ready["producer"],
        )

    mixed = register_clean_mix(
        p89_database,
        p90_ready,
        service,
        service.detail(production_id=production_id),
        alignment_source=AlignmentSource.FORCED_ALIGNMENT,
    )
    submitted = service.submit(
        production_id=production_id,
        expected_lock_version=mixed["production"]["lock_version"],
        actor=p90_ready["producer"],
    )
    action = service.add_review_action(
        production_id=production_id,
        request=ReviewActionRequest(
            expected_lock_version=submitted["production"]["lock_version"],
            audio_mix_version_id=submitted["production"]["current_mix_version_id"],
            paragraph_id=target_paragraph["id"],
            segment_take_id=new_take["id"],
            action_type=AudioReviewActionType.PACE,
            body="Confirm the regenerated paragraph pacing before approval.",
        ),
        actor=p90_ready["reviewer"],
    )
    with pytest.raises(psycopg.Error, match="Unresolved audio review actions"):
        service.decide(
            production_id=production_id,
            expected_lock_version=action["production"]["lock_version"],
            decision=AudioDecision.APPROVED,
            rationale="Attempt approval before resolving the pace action.",
            reviewer=p90_ready["reviewer"],
        )
    after_failed = service.detail(production_id=production_id)
    assert after_failed["decisions"] == []

    open_action = next(row for row in action["review_actions"] if row["resolved_at"] is None)
    resolved = service.resolve_review_action(
        production_id=production_id,
        action_id=open_action["id"],
        expected_lock_version=after_failed["production"]["lock_version"],
        actor=p90_ready["producer"],
    )
    approved = service.decide(
        production_id=production_id,
        expected_lock_version=resolved["production"]["lock_version"],
        decision=AudioDecision.APPROVED,
        rationale="All paragraph takes, forced timings, rights, loudness, peak, and review actions pass.",
        reviewer=p90_ready["reviewer"],
    )
    assert approved["production"]["status"] == "approved"
    assert approved["production"]["current_mix_status"] == "approved"
    assert all(take["external_fee_incurred"] is False for take in approved["takes"])
    assert all(float(take["actual_cost_usd"]) == 0 for take in approved["takes"])
    assert {
        take["timing_source"] for take in approved["takes"] if take["status"] == "selected"
    } == {"forced_alignment"}

    assembly = service.enqueue_assembly(
        production_id=production_id,
        request=AssemblyEnqueueRequest(
            expected_lock_version=approved["production"]["lock_version"]
        ),
        actor=p90_ready["producer"],
    )
    assert assembly["job"]["job_type"] == "assembly"
    assert float(assembly["job"]["estimated_cost_usd"]) == 0
    assert assembly["job"]["input_payload"]["audio_mix_version_id"] == str(
        approved["production"]["current_mix_version_id"]
    )


def test_proportional_preview_timing_cannot_be_finally_approved(p89_database, p90_ready) -> None:
    service, detail = initialize_and_select_takes(
        p89_database, p90_ready, timing_source=AlignmentSource.PROPORTIONAL_PREVIEW
    )
    mixed = register_clean_mix(
        p89_database,
        p90_ready,
        service,
        detail,
        alignment_source=AlignmentSource.PROPORTIONAL_PREVIEW,
    )
    submitted = service.submit(
        production_id=detail["production"]["id"],
        expected_lock_version=mixed["production"]["lock_version"],
        actor=p90_ready["producer"],
    )
    with pytest.raises(psycopg.Error, match="forced alignment"):
        service.decide(
            production_id=detail["production"]["id"],
            expected_lock_version=submitted["production"]["lock_version"],
            decision=AudioDecision.APPROVED,
            rationale="Attempt final approval using proportional preview timing.",
            reviewer=p90_ready["reviewer"],
        )
    current = service.detail(production_id=detail["production"]["id"])
    assert current["production"]["status"] == "in_review"
    assert current["decisions"] == []
