from datetime import datetime
from uuid import UUID

from pydantic import Field

from src.domain.asset_status import ApprovalStatus, AssetSourceType
from src.domain.base import FrozenRecord


class AssetRightsCreate(FrozenRecord):
    asset_id: UUID
    rights_basis: AssetSourceType = AssetSourceType.UNKNOWN
    supersedes_rights_id: UUID | None = None
    asset_owner: str | None = None
    licensor: str | None = None
    license_type: str | None = None
    license_version: str | None = None
    license_url: str | None = None
    terms_snapshot_uri: str | None = None
    terms_snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    commercial_use_allowed: bool = False
    editorial_use_allowed: bool = False
    modification_allowed: bool = False
    synthetic_edit_allowed: bool = False
    attribution_required: bool = False
    attribution_text: str | None = None
    territories: list[str] = Field(default_factory=lambda: ["worldwide"])
    platforms: list[str] = Field(default_factory=list)
    campaigns: list[str] = Field(default_factory=list)
    valid_from: datetime | None = None
    expires_at: datetime | None = None
    review_due_at: datetime | None = None
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None


class AssetRights(AssetRightsCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
