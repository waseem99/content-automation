from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord
from src.domain.render_status import RenderMode


class NarrationOutputCreate(FrozenRecord):
    workflow_run_id: UUID
    render_manifest_id: UUID | None = None
    stage_execution_id: UUID | None = None
    mode: RenderMode
    platform: str = Field(min_length=1)
    language: str = Field(min_length=1)
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_length: int = Field(ge=0)
    approved_voice_id: UUID | None = None
    provider: str = Field(min_length=1)
    provider_voice_id: str = Field(min_length=1)
    provider_request_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    output_asset_id: UUID | None = None
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NarrationOutput(NarrationOutputCreate):
    id: UUID
    created_at: datetime
