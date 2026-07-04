from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from src.domain.asset_enums import AssetType
from src.domain.asset_models import Asset
from src.domain.asset_status import AssetLifecycleStatus, AssetSourceType


class StorageMode(StrEnum):
    REFERENCE_IN_PLACE = "reference_in_place"
    COPY_TO_MANAGED_STORE = "copy_to_managed_store"


@dataclass(frozen=True, slots=True)
class FileInspection:
    path: Path
    sha256: str
    size_bytes: int
    mime_type: str | None
    original_filename: str
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class RegisterFileRequest:
    path: Path
    asset_type: AssetType
    source_type: AssetSourceType
    lifecycle_status: AssetLifecycleStatus
    storage_mode: StorageMode = StorageMode.REFERENCE_IN_PLACE
    parent_asset_id: UUID | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AssetRegistrationResult:
    asset: Asset
    created: bool
    inspected_path: Path


@dataclass(frozen=True, slots=True)
class AssetHandle:
    asset_id: UUID
    verified_path: Path


@dataclass(frozen=True, slots=True)
class ResolvedAsset:
    asset: Asset
    path: Path
