from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.assets.classification import AssetClassificationPolicy, AssetContext
from src.application.assets.exceptions import AssetNotFound
from src.application.assets.models import RegisterFileRequest, StorageMode
from src.application.assets.registry import AssetRegistryService
from src.domain.evidence_models import (
    RightsEvidence,
    RightsEvidenceCreate,
    RightsEvidenceType,
)
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class RightsEvidenceService:
    def __init__(
        self,
        database: Database,
        registry: AssetRegistryService,
        classification_policy: AssetClassificationPolicy | None = None,
    ) -> None:
        self.database = database
        self.registry = registry
        self.classification_policy = classification_policy or AssetClassificationPolicy()

    def register(
        self,
        *,
        target_asset_id: UUID,
        evidence_path: Path,
        evidence_type: RightsEvidenceType,
        source_url: str | None = None,
        uploaded_by: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RightsEvidence:
        classification = self.classification_policy.classify(AssetContext.RIGHTS_EVIDENCE)
        request = RegisterFileRequest(
            path=evidence_path,
            asset_type=classification.asset_type,
            source_type=classification.source_type,
            lifecycle_status=classification.lifecycle_status,
            storage_mode=StorageMode.COPY_TO_MANAGED_STORE,
            created_by=uploaded_by,
            metadata={"evidence_type": evidence_type.value, **(metadata or {})},
        )

        inspection = self.registry.inspect(request)
        with unit_of_work(self.database) as uow:
            if uow.assets.get_optional(target_asset_id) is None:
                raise AssetNotFound(f"Evidence target does not exist: {target_asset_id}")
            evidence_asset = self.registry.register_inspection_in_uow(
                uow,
                request,
                inspection,
            ).asset
            return uow.rights_evidence.create(
                RightsEvidenceCreate(
                    asset_id=target_asset_id,
                    evidence_asset_id=evidence_asset.id,
                    evidence_type=evidence_type,
                    storage_uri=evidence_asset.storage_uri,
                    sha256=evidence_asset.sha256,
                    source_url=source_url,
                    metadata=metadata or {},
                    uploaded_by=uploaded_by,
                )
            )
