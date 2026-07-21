from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import psycopg
import pytest

from src.application.generation_jobs.models import GenerationJobCompletion, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService
from src.application.releases import FinalReleaseService
from src.application.releases.models import (
    AssemblyEnqueueRequest,
    AssemblyOutputRequest,
    FinalReleaseCreate,
    PlaybackReviewRequest,
    QaEvaluateRequest,
    ReleaseDecisionRequest,
    ReleaseInputApprovalRequest,
    ReleaseInputRequest,
    RenderProfileRequest,
    TechnicalInspection,
)
from src.application.shared_storage.models import ArtifactVersionRequest
from src.application.shared_storage.service import _utcnow
from tests.integration.p96_release_support import p89_database, p96_ready


pytestmark = pytest.mark.integration


def release_profile() -> RenderProfileRequest:
    return RenderProfileRequest(
        profile_key="instagram-reel-1080x1920",
        display_name="Instagram Reel 1080 x 1920",
        platform="instagram",
        width=1080,
        height=1920,
        fps=Decimal("30"),
        container="mp4",
        video_codec="h264",
        audio_codec="aac",
        video_bitrate_kbps=8000,
        audio_bitrate_kbps=192,
        min_duration_seconds=Decimal("5"),
        max_duration_seconds=Decimal("90"),
        safe_area={"top": 180, "right": 80, "bottom": 320, "left": 80},
        captions_required=True,
        caption_format="burned_in",
        watermark_policy="forbidden",
        disclosure_required=True,
        target_loudness_lufs=Decimal("-14"),
        loudness_tolerance_lu=Decimal("2"),
        max_true_peak_dbfs=Decimal("-1"),
        max_av_sync_offset_ms=80,
        configuration={"deterministic_assembly": True, "phase": "P96"},
    )


def passing_inspection(output_hash: str, **overrides) -> TechnicalInspection:
    values = {
        "valid_container": True,
        "width": 1080,
        "height": 1920,
        "fps": Decimal("30"),
        "duration_seconds": Decimal("30"),
        "container": "mp4",
        "video_codec": "h264",
        "audio_codec": "aac",
        "video_bitrate_kbps": 9000,
        "audio_bitrate_kbps": 256,
        "has_audio": True,
        "captions_present": True,
        "caption_format": "burned_in",
        "disclosure_present": True,
        "watermark_present": False,
        "missing_frame_count": 0,
        "frozen_segment_count": 0,
        "black_frame_count": 0,
        "duplicate_shot_pairs": (),
        "caption_timing_violation_count": 0,
        "caption_clipping_detected": False,
        "safe_area_violation": False,
        "av_sync_offset_ms": 25,
        "integrated_loudness_lufs": Decimal("-14.5"),
        "true_peak_dbfs": Decimal("-1.5"),
        "audio_clipping_detected": False,
        "file_sha256": output_hash,
        "details": {"probe": "controlled-p96-inspection"},
    }
    values.update(overrides)
    return TechnicalInspection(**values)


def create_shared_input(ready, *, key: str, kind: str, asset_key: str):
    return ready["service"].create_artifact_version(
        request=ArtifactVersionRequest(
            brand_id=ready["brand_one"],
            portfolio_content_id=ready["content_one"],
            content_version=ready["content_one_version"],
            artifact_key=key,
            artifact_kind=kind,
            original_asset_id=ready["assets"][asset_key],
            backend_id=ready["shared_backend"]["id"],
            retention_until=_utcnow() + timedelta(days=90),
            metadata={"phase": "P96", "release_input": True},
        ),
        actor=ready["producer"],
    )["artifact"]


def approve_input(service, ready, artifact, role: str):
    return service.decide_input(
        ReleaseInputApprovalRequest(
            artifact_version_id=artifact["id"],
            role=role,
            decision="approved",
            rationale=f"The exact {role} artifact is approved for controlled final assembly.",
        ),
        actor=ready["reviewer"],
    )["approval"]


def test_final_release_blocks_bad_qa_then_seals_immutable_approved_manifest(
    p89_database,
    p96_ready,
) -> None:
    releases = FinalReleaseService(p89_database)
    jobs = GenerationJobService(p89_database)

    profile = releases.create_profile(release_profile(), actor=p96_ready["admin"])["profile"]
    profile = releases.activate_profile(profile_id=profile["id"], actor=p96_ready["admin"])["profile"]

    narration = create_shared_input(
        p96_ready,
        key="release/narration",
        kind="voiceover",
        asset_key="final_mix",
    )
    visual = create_shared_input(
        p96_ready,
        key="release/visual-001",
        kind="premium_clip",
        asset_key="visual",
    )
    branding = create_shared_input(
        p96_ready,
        key="release/branding",
        kind="thumbnail",
        asset_key="branding",
    )
    approve_input(releases, p96_ready, narration, "narration")
    approve_input(releases, p96_ready, visual, "visual_shot")
    approve_input(releases, p96_ready, branding, "branding")

    created = releases.create_release(
        FinalReleaseCreate(
            portfolio_content_id=p96_ready["content_one"],
            content_version=p96_ready["content_one_version"],
            render_profile_id=profile["id"],
            audio_mix_version_id=p96_ready["audio_mix_version_id"],
            inputs=(
                ReleaseInputRequest(
                    artifact_version_id=narration["id"],
                    role="narration",
                    sequence_number=0,
                ),
                ReleaseInputRequest(
                    artifact_version_id=visual["id"],
                    role="visual_shot",
                    sequence_number=1,
                ),
                ReleaseInputRequest(
                    artifact_version_id=branding["id"],
                    role="branding",
                    sequence_number=0,
                ),
            ),
            metadata={"release_label": "P96 acceptance release"},
        ),
        actor=p96_ready["producer"],
    )
    release_id = created["release"]["id"]
    assert created["release"]["status"] == "draft"
    assert created["release"]["audio_mix_version_id"] == p96_ready["audio_mix_version_id"]
    assert len(created["inputs"]) == 3

    enqueued = releases.enqueue_assembly(
        release_id=release_id,
        request=AssemblyEnqueueRequest(
            preferred_worker_id=p96_ready["producer"],
            max_attempts=2,
        ),
        actor=p96_ready["producer"],
    )
    assert enqueued["release"]["status"] == "assembly_queued"
    assert enqueued["job"]["job_type"] == "assembly"
    assert enqueued["job"]["input_payload"]["audio_mix_version_id"] == str(
        p96_ready["audio_mix_version_id"]
    )
    reused = releases.enqueue_assembly(
        release_id=release_id,
        request=AssemblyEnqueueRequest(preferred_worker_id=p96_ready["producer"]),
        actor=p96_ready["producer"],
    )
    assert reused["reused"] is True
    assert reused["job"]["id"] == enqueued["job"]["id"]

    output = p96_ready["service"].create_artifact_version(
        request=ArtifactVersionRequest(
            brand_id=p96_ready["brand_one"],
            portfolio_content_id=p96_ready["content_one"],
            content_version=p96_ready["content_one_version"],
            artifact_key="release/final-output",
            artifact_kind="final_video",
            original_asset_id=p96_ready["assets"]["output"],
            backend_id=p96_ready["shared_backend"]["id"],
            retention_until=_utcnow() + timedelta(days=180),
            metadata={"phase": "P96", "assembled": True},
        ),
        actor=p96_ready["producer"],
    )["artifact"]
    claimed = jobs.claim(
        worker_id=p96_ready["producer"],
        allowed_brand_ids=(p96_ready["brand_one"],),
        allowed_job_types=(GenerationJobType.ASSEMBLY,),
        requested_job_types=(GenerationJobType.ASSEMBLY,),
        providers=("local-assembly",),
    )
    assert claimed is not None
    completed = jobs.complete(
        GenerationJobCompletion(
            job_id=claimed["job"]["id"],
            attempt_id=claimed["attempt"]["id"],
            lease_token=claimed["lease_token"],
            worker_id=p96_ready["producer"],
            output_payload={
                "shared_artifact_version_id": str(output["id"]),
                "assembly_mode": "deterministic-release-assembler-v1",
            },
            provider_request_id="local-p96-assembly",
            actual_cost_usd=Decimal("0"),
        )
    )
    assert completed["job"]["status"] == "succeeded"

    assembled = releases.register_assembly_output(
        release_id=release_id,
        request=AssemblyOutputRequest(
            output_artifact_version_id=output["id"],
            generation_job_id=claimed["job"]["id"],
        ),
        actor=p96_ready["producer"],
    )
    assert assembled["release"]["status"] == "assembled"

    with p89_database.connection() as conn:
        output_hash = conn.execute(
            "SELECT sha256 FROM football_brief.assets WHERE id=%s",
            (output["original_asset_id"],),
        ).fetchone()["sha256"]

    blocked = releases.evaluate_qa(
        release_id=release_id,
        request=QaEvaluateRequest(
            inspection=passing_inspection(output_hash, black_frame_count=1),
            inspector_label="P96 controlled probe",
        ),
        actor=p96_ready["producer"],
    )
    assert blocked["ok"] is False
    assert blocked["release"]["status"] == "assembled"
    assert "BLACK_FRAMES" in blocked["qa_report"]["blocking_failures"]

    passed = releases.evaluate_qa(
        release_id=release_id,
        request=QaEvaluateRequest(
            inspection=passing_inspection(output_hash),
            inspector_label="P96 controlled probe",
        ),
        actor=p96_ready["producer"],
    )
    assert passed["ok"] is True
    assert passed["release"]["status"] == "qa_complete"

    submitted = releases.submit_playback_review(
        release_id=release_id,
        actor=p96_ready["producer"],
    )
    assert submitted["release"]["status"] == "in_review"
    checklist = {
        "full_playback_completed": True,
        "narration_intelligible": True,
        "visual_order_correct": True,
        "captions_readable": True,
        "branding_correct": True,
        "disclosures_visible": True,
        "no_unintended_content": True,
    }
    playback = releases.record_playback_review(
        release_id=release_id,
        request=PlaybackReviewRequest(
            decision="approved",
            checklist=checklist,
            rationale="Full end-to-end playback completed against the sealed platform profile.",
        ),
        reviewer=p96_ready["reviewer"],
    )
    assert playback["review"]["decision"] == "approved"

    approved = releases.decide_release(
        release_id=release_id,
        request=ReleaseDecisionRequest(
            decision="approved",
            rationale="Technical QA and mandatory full playback both passed.",
            expected_lock_version=submitted["release"]["lock_version"],
        ),
        reviewer=p96_ready["reviewer"],
    )
    release = approved["release"]
    assert release["status"] == "approved"
    assert release["manifest_hash"] is not None
    assert release["release_manifest"]["schema"] == "final-release-manifest-v1"
    assert release["release_manifest"]["audio_mix"]["id"] == p96_ready["audio_mix_version_id"]
    assert release["release_manifest"]["audio_mix"]["alignment_source"] == "forced_alignment"
    assert release["release_manifest"]["qa"]["outcome"] == "pass"
    assert release["release_manifest"]["playback_review"]["decision"] == "approved"

    with pytest.raises(psycopg.Error, match="immutable"):
        with p89_database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.final_releases SET total_cost_usd=99 WHERE id=%s",
                (release_id,),
            )

    revision = releases.create_release(
        FinalReleaseCreate(
            portfolio_content_id=p96_ready["content_one"],
            content_version=p96_ready["content_one_version"],
            render_profile_id=profile["id"],
            audio_mix_version_id=p96_ready["audio_mix_version_id"],
            inputs=(
                ReleaseInputRequest(artifact_version_id=narration["id"], role="narration"),
                ReleaseInputRequest(artifact_version_id=visual["id"], role="visual_shot", sequence_number=1),
                ReleaseInputRequest(artifact_version_id=branding["id"], role="branding"),
            ),
            metadata={"release_label": "P96 revision"},
        ),
        actor=p96_ready["producer"],
    )
    assert revision["release"]["version"] == 2
    assert revision["release"]["parent_release_id"] == release_id
    assert releases.detail(release_id=release_id)["release"]["status"] == "superseded"
