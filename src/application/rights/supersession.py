from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.rights.approval import RightsApprovalService
from src.domain.asset_status import ApprovalStatus
from src.domain.rights_models import AssetRights, AssetRightsCreate
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class RightsSupersessionService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_version(
        self,
        rights_id: UUID,
        overrides: dict[str, Any],
    ) -> AssetRights:
        with unit_of_work(self.database) as uow:
            previous = uow.rights_state.get(rights_id)
        payload = previous.model_dump(
            exclude={
                "id",
                "created_at",
                "updated_at",
                "approval_status",
                "approved_by",
                "approved_at",
                "rejection_reason",
                "supersedes_rights_id",
            }
        )
        payload.update(overrides)
        payload["asset_id"] = previous.asset_id
        payload["supersedes_rights_id"] = previous.id
        payload["approval_status"] = ApprovalStatus.PENDING
        return RightsApprovalService(self.database).create_pending(
            AssetRightsCreate.model_validate(payload)
        )
