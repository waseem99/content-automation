from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from src.domain.base import FrozenRecord
from src.domain.render_manifest_models import (
    ManifestDisclosure,
    ShortFormRenderPreset,
    VersionedHashReference,
)
from src.domain.render_status import ManifestAssetRole, RenderMode


class ManifestAssetInput(FrozenRecord):
    asset_id: UUID | None = None
    role: ManifestAssetRole
    sequence_number: int = Field(default=0, ge=0)
    placeholder_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_identity_or_placeholder(self) -> "ManifestAssetInput":
        if self.asset_id is None and not (self.placeholder_key or "").strip():
            raise ValueError("Manifest asset input requires asset_id or placeholder_key")
        if self.asset_id is not None and self.placeholder_key is not None:
            raise ValueError("Manifest asset input cannot combine asset and placeholder")
        return self


class RenderManifestBuildRequest(FrozenRecord):
    content_item_id: UUID
    workflow_run_id: UUID
    mode: RenderMode
    platform: str = Field(min_length=1)
    aspect_ratio: str = Field(min_length=1)
    script: VersionedHashReference
    storyboard: VersionedHashReference
    brand: VersionedHashReference
    policy: VersionedHashReference
    assets: tuple[ManifestAssetInput, ...]
    disclosures: tuple[ManifestDisclosure, ...] = ()
    preset: ShortFormRenderPreset = Field(default_factory=ShortFormRenderPreset)
    voice_asset_id: UUID | None = None
    music_asset_id: UUID | None = None
    rights_gate_evaluation_id: UUID | None = None
    approval_review_id: UUID | None = None
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> "RenderManifestBuildRequest":
        if self.mode == RenderMode.PUBLISH:
            if self.rights_gate_evaluation_id is None or self.approval_review_id is None:
                raise ValueError("Publish build requires rights evaluation and approval review")
            if any(item.asset_id is None for item in self.assets):
                raise ValueError("Publish build cannot contain placeholders")
        else:
            if self.rights_gate_evaluation_id is not None or self.approval_review_id is not None:
                raise ValueError("Preview build cannot claim publish approval")
        return self


class ManifestRenderContext(FrozenRecord):
    manifest_id: UUID
    render_job_id: UUID
    mode: RenderMode
    manifest: dict[str, Any]
    resolved_asset_paths: dict[UUID, str] = Field(default_factory=dict)
    placeholders: tuple[str, ...] = ()
    output_metadata: dict[str, Any] = Field(default_factory=dict)
