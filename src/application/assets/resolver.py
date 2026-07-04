from __future__ import annotations

from uuid import UUID

from src.application.assets.exceptions import (
    AssetHashMismatch,
    AssetNotFound,
    AssetStorageMissing,
    AssetUnavailable,
)
from src.application.assets.hashing import inspect_file
from src.application.assets.models import ResolvedAsset
from src.application.assets.storage import StorageUriResolver
from src.domain.asset_status import AssetLifecycleStatus
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class AssetResolver:
    def __init__(self, database: Database, storage_resolver: StorageUriResolver) -> None:
        self.database = database
        self.storage_resolver = storage_resolver

    def resolve(self, asset_id: UUID, *, verify_hash: bool = True) -> ResolvedAsset:
        with unit_of_work(self.database) as uow:
            asset = uow.assets.get_optional(asset_id)
        if asset is None:
            raise AssetNotFound(f"Asset does not exist: {asset_id}")
        if asset.lifecycle_status in {
            AssetLifecycleStatus.DELETED,
            AssetLifecycleStatus.EXPIRED,
        }:
            raise AssetUnavailable(
                f"Asset is not available: {asset_id} ({asset.lifecycle_status.value})"
            )

        path = self.storage_resolver.to_path(asset.storage_uri)
        if not path.is_file():
            raise AssetStorageMissing(f"Registered asset bytes are missing: {path}")
        if verify_hash:
            inspection = inspect_file(path)
            if inspection.sha256 != asset.sha256:
                raise AssetHashMismatch(
                    f"Asset bytes no longer match registry hash for {asset_id}"
                )
        return ResolvedAsset(asset=asset, path=path)
