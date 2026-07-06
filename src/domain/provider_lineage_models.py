from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord


class ProviderGenerationEvidenceCreate(FrozenRecord):
    provider_call_id: UUID
    output_asset_id: UUID
    parent_asset_id: UUID | None = None
    workflow_run_id: UUID
    stage_execution_id: UUID
    provider: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    prompt_name: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_id: str = Field(min_length=1)
    input_asset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderGenerationEvidence(ProviderGenerationEvidenceCreate):
    id: UUID
    created_at: datetime


class LineageNode(FrozenRecord):
    asset_id: UUID
    asset_sha256: str
    asset_type: str
    source_type: str
    parent_asset_id: UUID | None = None
    generation_evidence_id: UUID | None = None
    provider: str | None = None
    operation: str | None = None
    model_id: str | None = None
    provider_request_id: str | None = None
    prompt_hash: str | None = None
    depth: int = Field(ge=0)


class LineageReport(FrozenRecord):
    root_asset_id: UUID
    nodes: tuple[LineageNode, ...]
