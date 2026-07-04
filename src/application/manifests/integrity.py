from __future__ import annotations

from uuid import UUID

from src.application.assets.resolver import AssetResolver
from src.application.manifests.canonical import manifest_hash
from src.application.manifests.exceptions import ManifestIntegrityError
from src.domain.render_manifest_models import RenderManifestRecord
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class ManifestIntegrityVerifier:
    def __init__(self, database: Database, asset_resolver: AssetResolver) -> None:
        self.database = database
        self.asset_resolver = asset_resolver

    def verify(self, manifest_id: UUID) -> tuple[RenderManifestRecord, dict[UUID, str]]:
        with unit_of_work(self.database) as uow:
            record = uow.render_manifests.get(manifest_id)
            stored_assets = uow.render_manifests.list_assets(manifest_id)

        actual_hash = manifest_hash(record.document)
        if actual_hash != record.manifest_hash:
            raise ManifestIntegrityError("Stored manifest JSON does not match manifest hash")

        document_assets = {
            asset.asset_id: asset
            for asset in record.document.assets
            if asset.asset_id is not None
        }
        stored_by_id = {row["asset_id"]: row for row in stored_assets}
        if set(document_assets) != set(stored_by_id):
            raise ManifestIntegrityError("Manifest JSON and manifest asset rows differ")

        resolved: dict[UUID, str] = {}
        for asset_id, reference in document_assets.items():
            stored = stored_by_id[asset_id]
            if stored["asset_sha256"] != reference.asset_sha256:
                raise ManifestIntegrityError("Manifest asset row hash differs from document")
            if stored["asset_rights_id"] != reference.asset_rights_id:
                raise ManifestIntegrityError("Manifest asset rights differ from document")
            result = self.asset_resolver.resolve(asset_id, verify_hash=True)
            if result.asset.sha256 != reference.asset_sha256:
                raise ManifestIntegrityError("Current asset hash differs from manifest")
            resolved[asset_id] = str(result.path)
        return record, resolved
