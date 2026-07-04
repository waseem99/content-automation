from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from src.domain.base import FrozenRecord
from src.domain.render_status import (
    ManifestAssetRole,
    RenderManifestStatus,
    RenderMode,
)


class VersionedHashReference(FrozenRecord):
    version: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    storage_uri: str | None = None


class ManifestAssetReference(FrozenRecord):
    asset_id: UUID | None = None
    asset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    asset_rights_id: UUID | None = None
    rights_evidence_ids: tuple[UUID, ...] = ()
    role: ManifestAssetRole
    sequence_number: int = Field(default=0, ge=0)
    parent_asset_id: UUID | None = None
    placeholder_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_asset_or_placeholder(self) -> "ManifestAssetReference":
        has_asset = self.asset_id is not None or self.asset_sha256 is not None
        has_placeholder = bool((self.placeholder_key or "").strip())
        if has_asset and has_placeholder:
            raise ValueError("Manifest asset cannot be both canonical and a placeholder")
        if not has_asset and not has_placeholder:
            raise ValueError("Manifest asset requires canonical identity or placeholder_key")
        if has_asset and (self.asset_id is None or self.asset_sha256 is None):
            raise ValueError("Canonical manifest asset requires both asset_id and asset_sha256")
        return self

    @property
    def is_placeholder(self) -> bool:
        return self.asset_id is None


class ManifestDisclosure(FrozenRecord):
    code: str = Field(min_length=1)
    text: str = Field(min_length=1)
    required: bool = True


class ManifestApprovalReference(FrozenRecord):
    human_review_id: UUID
    reviewer: str = Field(min_length=1)
    approved_at: datetime


class RightsEvaluationReference(FrozenRecord):
    evaluation_id: UUID
    policy_version: str = Field(min_length=1)
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ShortFormRenderPreset(FrozenRecord):
    preset_id: str = "short-form-editorial-v1"
    width: int = Field(default=1080, gt=0)
    height: int = Field(default=1920, gt=0)
    fps: int = Field(default=30, gt=0)
    hook_starts_at_frame_one: bool = True
    pre_hook_intro_duration_sec: float = Field(default=0.0, ge=0.0)
    logo_sting_duration_sec: float = Field(default=0.5, ge=0.3, le=0.7)
    logo_sting_placement: str = "inside_or_after_hook"

    @model_validator(mode="after")
    def enforce_frame_one_hook(self) -> "ShortFormRenderPreset":
        if not self.hook_starts_at_frame_one:
            raise ValueError("Short-form publish preset must start the hook at frame one")
        if self.pre_hook_intro_duration_sec != 0:
            raise ValueError("Dedicated pre-hook intros are not allowed")
        return self


class RenderManifestDocument(FrozenRecord):
    schema_version: str = "1.0.0"
    content_item_id: UUID
    workflow_run_id: UUID
    manifest_version: int = Field(ge=1)
    mode: RenderMode
    platform: str = Field(min_length=1)
    aspect_ratio: str = Field(min_length=1)
    script: VersionedHashReference
    storyboard: VersionedHashReference
    brand: VersionedHashReference
    policy: VersionedHashReference
    preset: ShortFormRenderPreset = Field(default_factory=ShortFormRenderPreset)
    voice_asset_id: UUID | None = None
    music_asset_id: UUID | None = None
    assets: tuple[ManifestAssetReference, ...] = ()
    disclosures: tuple[ManifestDisclosure, ...] = ()
    rights_evaluation: RightsEvaluationReference | None = None
    approval: ManifestApprovalReference | None = None
    not_for_publication: bool
    watermark_text: str | None = None
    output_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mode_contract(self) -> "RenderManifestDocument":
        if self.mode == RenderMode.PREVIEW:
            if not self.not_for_publication:
                raise ValueError("Preview manifest must be marked not for publication")
            if not (self.watermark_text or "").strip():
                raise ValueError("Preview manifest requires a visible watermark")
            if self.approval is not None or self.rights_evaluation is not None:
                raise ValueError("Preview manifest must not claim publish approval")
        else:
            if self.not_for_publication:
                raise ValueError("Publish manifest cannot be marked not for publication")
            if self.watermark_text is not None:
                raise ValueError("Publish manifest cannot carry a preview watermark")
            if self.approval is None or self.rights_evaluation is None:
                raise ValueError("Publish manifest requires approval and rights evaluation")
            if any(asset.is_placeholder for asset in self.assets):
                raise ValueError("Publish manifest cannot contain placeholders")
            if any(asset.asset_rights_id is None for asset in self.assets):
                raise ValueError("Every publish asset requires selected rights")
        return self


class RenderManifestCreate(FrozenRecord):
    document: RenderManifestDocument
    parent_manifest_id: UUID | None = None
    material_input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class RenderManifestRecord(RenderManifestCreate):
    id: UUID
    status: RenderManifestStatus
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
