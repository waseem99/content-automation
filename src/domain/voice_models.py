from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.asset_status import ApprovalStatus
from src.domain.base import FrozenRecord


class VoiceType(StrEnum):
    PREMADE = "premade"
    LICENSED_SYNTHETIC = "licensed_synthetic"
    HUMAN_RECORDED = "human_recorded"
    CLONED = "cloned"


class ApprovedVoiceCreate(FrozenRecord):
    provider: str = Field(min_length=1)
    provider_voice_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    voice_type: VoiceType
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    consent_evidence_asset_id: UUID | None = None
    allowed_languages: list[str] = Field(default_factory=lambda: ["en"])
    allowed_platforms: list[str] = Field(default_factory=list)
    prohibited_uses: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovedVoice(ApprovedVoiceCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
