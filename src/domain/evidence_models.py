from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord


class RightsEvidenceType(StrEnum):
    LICENSE = "license"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    CONSENT = "consent"
    SOURCE_SNAPSHOT = "source_snapshot"
    TERMS_SNAPSHOT = "terms_snapshot"
    ATTRIBUTION_RECORD = "attribution_record"
    OTHER = "other"


class RightsEvidenceCreate(FrozenRecord):
    asset_id: UUID
    evidence_asset_id: UUID
    evidence_type: RightsEvidenceType
    storage_uri: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    uploaded_by: str | None = None


class RightsEvidence(RightsEvidenceCreate):
    id: UUID
    created_at: datetime
