from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.asset_enums import AssetType
from src.domain.asset_status import AssetLifecycleStatus, AssetSourceType
from src.domain.base import FrozenRecord


class AssetCreate(FrozenRecord):
    asset_type: AssetType
    source_type: AssetSourceType = AssetSourceType.UNKNOWN
    lifecycle_status: AssetLifecycleStatus = AssetLifecycleStatus.CANDIDATE
    storage_uri: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    parent_asset_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None


class Asset(AssetCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
