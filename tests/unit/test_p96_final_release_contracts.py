from pathlib import Path

import pytest
from pydantic import ValidationError

from src.application.releases import FinalReleaseService, RouteBoundFinalReleaseService
from src.application.releases.models import (
    FinalReleaseCreate,
    PlaybackReviewRequest,
    ReleaseInputRequest,
    RenderProfileRequest,
)


ROOT = Path(__file__).resolve().parents[2]
FOUNDATION = ROOT / "migrations/0068_final_release_foundation.sql"
INTEGRITY = ROOT / "migrations/0069_final_release_integrity.sql"
AVAILABILITY = ROOT / "migrations/0070_final_release_availability_and_qa_retry.sql"
ROUTING = ROOT / "migrations/0071_final_release_routing_integrity.sql"
AUDIO = ROOT / "migrations/0072_final_release_audio_mix_integrity.sql"
ROUTE_OUTPUTS = ROOT / "migrations/0073_final_release_exact_route_outputs.sql"
SERVICE = ROOT / "src/application/releases/service.py"
VALIDATED = ROOT / "src/application/releases/validated_service.py"
AUDIO_SERVICE = ROOT / "src/application/releases/audio_bound_service.py"
ROUTE_SERVICE = ROOT / "src/application/releases/route_bound_service.py"
API = ROOT / "src/operator_api/releases_runtime.py"


def profile_payload(**overrides):
    payload = {
        "profile_key": "vertical-release",
        "display_name": "Vertical Release",
        "platform": "instagram",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "container": "mp4",
        "video_codec": "h264",
        "audio_codec": "aac",
        "video_bitrate_kbps": 8000,
        "audio_bitrate_kbps": 192,
        "max_duration_seconds": 90,
        "safe_area": {"top": 180, "right": 80, "bottom": 320, "left": 80},
    }
    payload.update(overrides)
    return payload


def test_public_release_service_uses_route_and_audio_bound_contract() -> None:
    assert FinalReleaseService is RouteBoundFinalReleaseService


def test_profile_rejects_invalid_safe_area_and_duration_contracts() -> None:
    normalized = RenderProfileRequest(**profile_payload(profile_key="  VERTICAL-RELEASE  "))
    assert normalized.profile_key == "vertical-release"
    with pytest.raises(ValidationError, match="horizontal safe area"):
        RenderProfileRequest(
            **profile_payload(safe_area={"top": 0, "right": 600, "bottom": 0, "left": 600})
        )
    with pytest.raises(ValidationError, match="greater than or equal"):
        RenderProfileRequest(**profile_payload(min_duration_seconds=91, max_duration_seconds=90))


def test_release_requires_audio_mix_narration_visual_and_branding_inputs() -> None:
    with pytest.raises(ValidationError, match="required release roles"):
        FinalReleaseCreate(
            portfolio_content_id="00000000-0000-0000-0000-000000000001",
            content_version=1,
            render_profile_id="00000000-0000-0000-0000-000000000002",
            audio_mix_version_id="00000000-0000-0000-0000-000000000004",
            inputs=(
                ReleaseInputRequest(
                    artifact_version_id="00000000-0000-0000-0000-000000000003",
                    role="narration",
                ),
            ),
        )


def test_playback_approval_requires_full_checklist_pass() -> None:
    checklist = {
        "full_playback_completed": True,
        "narration_intelligible": True,
        "visual_order_correct": True,
        "captions_readable": True,
        "branding_correct": False,
        "disclosures_visible": True,
        "no_unintended_content": True,
    }
    with pytest.raises(ValidationError, match="every checklist item"):
        PlaybackReviewRequest(
            decision="approved",
            checklist=checklist,
            rationale="Branding did not pass.",
        )


def test_database_binds_exact_inputs_job_qa_playback_and_manifest() -> None:
    source = FOUNDATION.read_text(encoding="utf-8") + INTEGRITY.read_text(encoding="utf-8")
    assert "final_release_input_approvals" in source
    assert "final_release_inputs" in source
    assert "assembly_job_id" in source
    assert "final_release_qa_reports" in source
    assert "final_release_playback_reviews" in source
    assert "release_manifest" in source
    assert "Final release approval requires current inputs" in source
    assert "Approved and superseded final releases are immutable" in source


def test_release_requires_exact_current_approved_p90_audio_mix() -> None:
    source = AUDIO.read_text(encoding="utf-8")
    audio_service = AUDIO_SERVICE.read_text(encoding="utf-8")
    assert "audio_mix_version_id" in source
    assert "current approved QC-passing forced-alignment audio mix" in source
    assert "Narration release input must be the exact approved final-mix asset" in source
    assert '"audio_mix_version_id": str(release["audio_mix_version_id"])' in audio_service
    assert 'manifest["audio_mix"]' in audio_service


def test_qa_retry_and_shared_object_availability_are_fail_closed() -> None:
    source = AVAILABILITY.read_text(encoding="utf-8")
    validated = VALIDATED.read_text(encoding="utf-8")
    assert "Only passing technical QA can advance a final release" in source
    assert "exact available shared original object" in source
    assert "Technical QA requires the exact available shared output object" in source
    assert "Final approval requires current approved inputs and available shared media" in source
    assert "if outcome == \"pass\"" in validated
    assert "reused" in validated


def test_mixed_routing_requires_complete_mapping_and_settled_managed_jobs() -> None:
    source = ROUTING.read_text(encoding="utf-8")
    validated = VALIDATED.read_text(encoding="utf-8")
    assert "Every approved routing item requires one exact visual release input" in source
    assert "Managed routing items must have reconciled successful generation jobs" in source
    assert "final_release_routing_inputs_incomplete" in validated
    assert "final_release_managed_routes_not_settled" in validated


def test_route_outputs_bind_selected_candidate_or_managed_shared_artifact() -> None:
    source = ROUTE_OUTPUTS.read_text(encoding="utf-8")
    route_service = ROUTE_SERVICE.read_text(encoding="utf-8")
    assert "final_release_one_visual_per_routing_item_idx" in source
    assert "Local visual input must use the exact selected routing candidate asset" in source
    assert "Managed visual input must be the exact reconciled successful job output artifact" in source
    assert "managed_artifact_version_id" in route_service
    assert "final_release_route_outputs_mismatch" in route_service


def test_release_api_keeps_configuration_admin_and_review_decisions_scoped() -> None:
    source = API.read_text(encoding="utf-8")
    assert '@app.post("/release-profiles")' in source
    assert "require_admin(operator)" in source
    assert '@app.post("/releases/{release_id}/assembly")' in source
    assert "AccessPermission.RUN_PRODUCTION" in source
    assert '@app.post("/releases/{release_id}/playback-review")' in source
    assert "AccessPermission.REVIEW_CONTENT" in source


def test_no_automatic_publication_or_live_provider_controls_are_added() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (SERVICE, VALIDATED, AUDIO_SERVICE, ROUTE_SERVICE, API)
    ).lower()
    assert "youtube" not in combined
    assert "facebook" not in combined
    assert '@app.post("/publish' not in combined
    assert 'def publish' not in combined
    assert "aws_secret" not in combined
    assert "api_key" not in combined
