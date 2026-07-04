from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.domain.render_manifest_models import (
    ManifestApprovalReference,
    ManifestAssetReference,
    RenderManifestDocument,
    RightsEvaluationReference,
    ShortFormRenderPreset,
    VersionedHashReference,
)
from src.domain.render_status import ManifestAssetRole, RenderMode


def _ref(character: str) -> VersionedHashReference:
    return VersionedHashReference(version="1", content_hash=character * 64)


def _base() -> dict:
    return {
        "content_item_id": uuid4(),
        "workflow_run_id": uuid4(),
        "manifest_version": 1,
        "platform": "youtube",
        "aspect_ratio": "9:16",
        "script": _ref("a"),
        "storyboard": _ref("b"),
        "brand": _ref("c"),
        "policy": _ref("d"),
    }


def test_preview_requires_watermark_and_non_publication_marker() -> None:
    values = _base()
    values.update(
        mode=RenderMode.PREVIEW,
        assets=(
            ManifestAssetReference(
                role=ManifestAssetRole.IMAGE,
                placeholder_key="placeholder",
            ),
        ),
        not_for_publication=True,
        watermark_text="PREVIEW - NOT FOR PUBLICATION",
    )
    document = RenderManifestDocument(**values)
    assert document.assets[0].is_placeholder

    values["watermark_text"] = None
    with pytest.raises(ValidationError):
        RenderManifestDocument(**values)


def test_publish_rejects_placeholders_and_requires_approval() -> None:
    values = _base()
    values.update(
        mode=RenderMode.PUBLISH,
        assets=(
            ManifestAssetReference(
                role=ManifestAssetRole.IMAGE,
                placeholder_key="placeholder",
            ),
        ),
        not_for_publication=False,
    )
    with pytest.raises(ValidationError):
        RenderManifestDocument(**values)


def test_valid_publish_manifest_has_rights_and_human_approval() -> None:
    asset_id = uuid4()
    values = _base()
    values.update(
        mode=RenderMode.PUBLISH,
        assets=(
            ManifestAssetReference(
                asset_id=asset_id,
                asset_sha256="e" * 64,
                asset_rights_id=uuid4(),
                rights_evidence_ids=(uuid4(),),
                role=ManifestAssetRole.IMAGE,
            ),
        ),
        rights_evaluation=RightsEvaluationReference(
            evaluation_id=uuid4(),
            policy_version="1",
            policy_hash="f" * 64,
            territory="US",
            requested_uses=("commercial",),
        ),
        approval=ManifestApprovalReference(
            human_review_id=uuid4(),
            reviewer="reviewer",
            approved_at=datetime.now(timezone.utc),
        ),
        not_for_publication=False,
    )
    document = RenderManifestDocument(**values)
    assert document.mode == RenderMode.PUBLISH


def test_short_form_preset_rejects_pre_hook_intro() -> None:
    with pytest.raises(ValidationError):
        ShortFormRenderPreset(pre_hook_intro_duration_sec=4.0)
    preset = ShortFormRenderPreset(logo_sting_duration_sec=0.5)
    assert preset.hook_starts_at_frame_one is True
