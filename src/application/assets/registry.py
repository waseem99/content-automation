from __future__ import annotations

from pathlib import Path

from src.application.assets.exceptions import InvalidAssetPath, InvalidParentAsset
from src.application.assets.hashing import inspect_file
from src.application.assets.models import (
    AssetRegistrationResult,
    FileInspection,
    RegisterFileRequest,
    StorageMode,
)
from src.application.assets.storage import ManagedAssetStore, StorageUriResolver
from src.domain.asset_models import AssetCreate
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import PostgresUnitOfWork, unit_of_work


class AssetRegistryService:
    def __init__(
        self,
        database: Database,
        storage_resolver: StorageUriResolver,
        managed_store: ManagedAssetStore | None = None,
    ) -> None:
        self.database = database
        self.storage_resolver = storage_resolver
        self.managed_store = managed_store or ManagedAssetStore(storage_resolver)

    def inspect(self, request: RegisterFileRequest) -> FileInspection:
        return inspect_file(request.path)

    def register_file(self, request: RegisterFileRequest) -> AssetRegistrationResult:
        inspection = self.inspect(request)
        with unit_of_work(self.database) as uow:
            return self.register_inspection_in_uow(uow, request, inspection)

    def register_file_in_uow(
        self,
        uow: PostgresUnitOfWork,
        request: RegisterFileRequest,
    ) -> AssetRegistrationResult:
        return self.register_inspection_in_uow(uow, request, self.inspect(request))

    def register_inspection_in_uow(
        self,
        uow: PostgresUnitOfWork,
        request: RegisterFileRequest,
        inspection: FileInspection,
    ) -> AssetRegistrationResult:
        requested_path = request.path.expanduser().resolve(strict=True)
        if inspection.path != requested_path:
            raise InvalidAssetPath(
                "File inspection does not belong to the requested registration path"
            )
        if request.parent_asset_id is not None:
            parent = uow.assets.get_optional(request.parent_asset_id)
            if parent is None:
                raise InvalidParentAsset(
                    f"Parent asset does not exist: {request.parent_asset_id}"
                )

        registered_path, storage_uri = self._store(request, inspection)
        data = AssetCreate(
            asset_type=request.asset_type,
            source_type=request.source_type,
            lifecycle_status=request.lifecycle_status,
            original_filename=inspection.original_filename,
            storage_uri=storage_uri,
            sha256=inspection.sha256,
            mime_type=inspection.mime_type,
            size_bytes=inspection.size_bytes,
            parent_asset_id=request.parent_asset_id,
            metadata={
                **request.metadata,
                "registered_mtime_ns": inspection.mtime_ns,
                "storage_mode": request.storage_mode.value,
            },
            created_by=request.created_by,
        )
        asset, created = uow.assets.create_or_get(data)
        return AssetRegistrationResult(
            asset=asset,
            created=created,
            inspected_path=registered_path,
        )

    def _store(
        self,
        request: RegisterFileRequest,
        inspection: FileInspection,
    ) -> tuple[Path, str]:
        if request.storage_mode == StorageMode.COPY_TO_MANAGED_STORE:
            return self.managed_store.copy(inspection)
        uri = self.storage_resolver.workspace_uri(inspection.path)
        return inspection.path, uri
