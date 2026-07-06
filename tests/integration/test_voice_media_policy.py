from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from psycopg.errors import CheckViolation, RaiseException

from src.application.assets.classification import AssetContext
from src.application.media.asset_policy import MediaAssetPolicyService
from src.application.media.models import MediaAssetUseRequest, VoiceSynthesisAuditRequest, VoiceUseRequest
from src.application.media.narration_audit import NarrationAuditService, text_hash
from src.application.media.policy_errors import MediaAssetPolicyFailure, VoicePolicyFailure
from src.application.media.voice_policy import VoicePolicyService
from src.domain.asset_enums import AssetType
from src.domain.asset_models import AssetCreate
from src.domain.asset_status import ApprovalStatus, AssetLifecycleStatus, AssetSourceType
from src.domain.render_status import RenderMode
from src.domain.voice_models import ApprovedVoiceCreate, VoiceType
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import (
    approve_rights,
    close_database,
    create_workflow,
    database_fixture,
    gate_for,
    register_asset,
    registry_for,
)


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _approved_voice(database, *, provider_voice_id="voice-approved", preview_only=False, status=ApprovalStatus.APPROVED, expires_at=None):
    with unit_of_work(database) as uow:
        return uow.approved_voices.create(
            ApprovedVoiceCreate(
                provider="elevenlabs",
                provider_voice_id=provider_voice_id,
                display_name="Approved Narrator",
                voice_type=VoiceType.PREMADE,
                approval_status=status,
                allowed_languages=["en"],
                allowed_platforms=["youtube"],
                prohibited_uses=["real_person_mimicry"],
                expires_at=expires_at,
                approved_by="pytest" if status == ApprovalStatus.APPROVED else None,
                approved_at=datetime.now(timezone.utc) if status == ApprovalStatus.APPROVED else None,
                preview_only=preview_only,
            )
        )


def _consent_asset(database):
    with unit_of_work(database) as uow:
        return uow.assets.create(
            AssetCreate(
                asset_type=AssetType.LICENSE_EVIDENCE,
                source_type=AssetSourceType.CLIENT_SUPPLIED,
                lifecycle_status=AssetLifecycleStatus.INTERNAL_ONLY,
                storage_uri="workspace:///consent.pdf",
                sha256="c" * 64,
                metadata={"evidence_type": "consent"},
                created_by="pytest",
            )
        )


def test_publish_rejects_raw_provider_voice_id(database) -> None:
    with pytest.raises(VoicePolicyFailure, match="approved internal voice"):
        VoicePolicyService(database).authorize(
            VoiceUseRequest(
                mode=RenderMode.PUBLISH,
                provider="elevenlabs",
                provider_voice_id="env-only-voice",
                platform="youtube",
                requested_by="pytest",
            )
        )


def test_publish_accepts_approved_internal_voice_id(database) -> None:
    voice = _approved_voice(database)
    decision = VoicePolicyService(database).authorize(
        VoiceUseRequest(
            mode=RenderMode.PUBLISH,
            provider="elevenlabs",
            approved_voice_id=voice.id,
            platform="youtube",
            requested_by="pytest",
        )
    )
    assert decision.provider_voice_id == voice.provider_voice_id
    assert decision.development_voice is False


def test_preview_development_voice_must_be_explicit(database) -> None:
    policy = VoicePolicyService(database)
    with pytest.raises(VoicePolicyFailure):
        policy.authorize(
            VoiceUseRequest(
                mode=RenderMode.PREVIEW,
                provider="elevenlabs",
                provider_voice_id="dev-voice",
                platform="youtube",
                requested_by="pytest",
            )
        )
    decision = policy.authorize(
        VoiceUseRequest(
            mode=RenderMode.PREVIEW,
            provider="elevenlabs",
            provider_voice_id="dev-voice",
            platform="youtube",
            allow_development_voice=True,
            requested_by="pytest",
        )
    )
    assert decision.development_voice is True


def test_preview_only_or_expired_voice_cannot_publish(database) -> None:
    preview_voice = _approved_voice(database, provider_voice_id="preview-only", preview_only=True)
    expired = _approved_voice(
        database,
        provider_voice_id="expired",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    policy = VoicePolicyService(database)
    for voice in (preview_voice, expired):
        with pytest.raises(VoicePolicyFailure):
            policy.authorize(
                VoiceUseRequest(
                    mode=RenderMode.PUBLISH,
                    provider="elevenlabs",
                    approved_voice_id=voice.id,
                    platform="youtube",
                    requested_by="pytest",
                )
            )


def test_approved_cloned_voice_requires_canonical_consent_asset(database) -> None:
    with pytest.raises((CheckViolation, RaiseException), match="consent"):
        with unit_of_work(database) as uow:
            uow.approved_voices.create(
                ApprovedVoiceCreate(
                    provider="elevenlabs",
                    provider_voice_id="clone-no-consent",
                    display_name="No Consent Clone",
                    voice_type=VoiceType.CLONED,
                    approval_status=ApprovalStatus.APPROVED,
                    approved_by="pytest",
                    approved_at=datetime.now(timezone.utc),
                )
            )

    consent = _consent_asset(database)
    with unit_of_work(database) as uow:
        approved = uow.approved_voices.create(
            ApprovedVoiceCreate(
                provider="elevenlabs",
                provider_voice_id="clone-with-consent",
                display_name="Consented Clone",
                voice_type=VoiceType.CLONED,
                approval_status=ApprovalStatus.APPROVED,
                consent_evidence_asset_id=consent.id,
                approved_by="pytest",
                approved_at=datetime.now(timezone.utc),
            )
        )
    assert approved.consent_evidence_asset_id == consent.id


def test_narration_audit_records_text_voice_provider_and_output(database) -> None:
    voice = _approved_voice(database)
    workflow_id = create_workflow(database)
    with unit_of_work(database) as uow:
        output = uow.assets.create(
            AssetCreate(
                asset_type=AssetType.VOICE,
                source_type=AssetSourceType.AI_GENERATED,
                lifecycle_status=AssetLifecycleStatus.APPROVED,
                storage_uri="managed://voice/output.mp3",
                sha256="a" * 64,
                created_by="pytest",
            )
        )
    record = NarrationAuditService(database).record(
        VoiceSynthesisAuditRequest(
            workflow_run_id=workflow_id,
            mode=RenderMode.PUBLISH,
            provider="elevenlabs",
            provider_voice_id=voice.provider_voice_id,
            provider_request_id="req-001",
            model_id="eleven_multilingual_v2",
            platform="youtube",
            text="Hello football world",
            approved_voice_id=voice.id,
            output_asset_id=output.id,
            output_sha256=output.sha256,
            created_by="pytest",
        )
    )
    assert record.text_hash == text_hash("Hello football world")
    assert record.approved_voice_id == voice.id
    assert record.output_asset_id == output.id


def test_music_requires_approved_platform_rights(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    registry = registry_for(database, tmp_path)
    music = tmp_path / "music.mp3"
    evidence = tmp_path / "music-license.pdf"
    music.write_bytes(b"music-bytes")
    evidence.write_bytes(b"music-license")
    asset = register_asset(registry, music, AssetContext.BACKGROUND_MUSIC)

    service = MediaAssetPolicyService(database, gate_for(database, tmp_path))
    with pytest.raises(MediaAssetPolicyFailure):
        service.authorize(
            MediaAssetUseRequest(
                mode=RenderMode.PUBLISH,
                workflow_run_id=workflow_id,
                asset_ids=(asset.id,),
                role="music",
                platform="youtube",
                evaluated_by="pytest",
            )
        )

    approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
        platforms=["youtube"],
        territories=["worldwide"],
    )
    decision = service.authorize(
        MediaAssetUseRequest(
            mode=RenderMode.PUBLISH,
            workflow_run_id=workflow_id,
            asset_ids=(asset.id,),
            role="music",
            platform="youtube",
            evaluated_by="pytest",
        )
    )
    assert decision.outcome.value == "pass"


def test_font_role_requires_font_asset_type(database, tmp_path: Path) -> None:
    workflow_id = create_workflow(database)
    registry = registry_for(database, tmp_path)
    music = tmp_path / "not-font.mp3"
    music.write_bytes(b"not-a-font")
    asset = register_asset(registry, music, AssetContext.BACKGROUND_MUSIC)
    with pytest.raises(MediaAssetPolicyFailure, match="type"):
        MediaAssetPolicyService(database, gate_for(database, tmp_path)).authorize(
            MediaAssetUseRequest(
                mode=RenderMode.PUBLISH,
                workflow_run_id=workflow_id,
                asset_ids=(asset.id,),
                role="font",
                platform="youtube",
                evaluated_by="pytest",
            )
        )
