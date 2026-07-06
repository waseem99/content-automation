from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.asset_enums import AssetType
from src.domain.base import FrozenRecord


class ProviderCallCreate(FrozenRecord):
    stage_execution_id: UUID
    provider: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    provider_request_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    units: float | None = Field(default=None, ge=0)
    unit_name: str | None = None
    cost_usd: float = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DerivativeRegistrationRequest(FrozenRecord):
    workflow_run_id: UUID
    stage_execution_id: UUID
    parent_asset_id: UUID
    output_path: Path
    output_asset_type: AssetType
    provider: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    prompt_name: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_call: ProviderCallCreate
    platform: str = Field(default="youtube", min_length=1)
    territory: str = Field(default="worldwide", min_length=1)
    campaign: str | None = None
    created_by: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    allow_reuse: bool = True
    require_modification_rights: bool = True
    require_synthetic_edit_rights: bool = True


class DerivativeRegistrationResult(FrozenRecord):
    asset_id: UUID
    evidence_id: UUID
    reused: bool
