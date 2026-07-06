from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from src.domain.base import FrozenRecord
from src.domain.render_status import RenderMode
from src.domain.voice_models import ApprovedVoice


class VoiceUseRequest(FrozenRecord):
    mode: RenderMode
    provider: str = Field(min_length=1)
    provider_voice_id: str | None = None
    approved_voice_id: UUID | None = None
    language: str = Field(default="en", min_length=1)
    platform: str = Field(min_length=1)
    use_case: str = Field(default="editorial_narration", min_length=1)
    allow_development_voice: bool = False
    requested_by: str = Field(min_length=1)

    @field_validator("language", "platform", "use_case")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip().lower()


class VoiceUseDecision(FrozenRecord):
    voice: ApprovedVoice | None
    provider: str
    provider_voice_id: str
    development_voice: bool
    mode: RenderMode


class MediaAssetUseRequest(FrozenRecord):
    mode: RenderMode
    workflow_run_id: UUID
    asset_ids: tuple[UUID, ...]
    role: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    territory: str = Field(default="worldwide", min_length=1)
    campaign: str | None = None
    commercial_use: bool = True
    editorial_use: bool = True
    modification: bool = False
    synthetic_edit: bool = False
    evaluated_by: str = Field(min_length=1)


class VoiceSynthesisAuditRequest(FrozenRecord):
    workflow_run_id: UUID
    mode: RenderMode
    provider: str = Field(min_length=1)
    provider_voice_id: str = Field(min_length=1)
    provider_request_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    language: str = Field(default="en", min_length=1)
    platform: str = Field(min_length=1)
    text: str
    approved_voice_id: UUID | None = None
    output_asset_id: UUID | None = None
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    render_manifest_id: UUID | None = None
    stage_execution_id: UUID | None = None
    created_by: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
