from __future__ import annotations

from uuid import UUID

from src.domain.asset_status import ApprovalStatus
from src.domain.rights_models import AssetRights
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class RightsStatusService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def reject(self, rights_id: UUID, reason: str) -> AssetRights:
        return self._set(rights_id, ApprovalStatus.REJECTED, reason)

    def revoke(self, rights_id: UUID, reason: str) -> AssetRights:
        return self._set(rights_id, ApprovalStatus.REVOKED, reason)

    def expire(self, rights_id: UUID, reason: str = "Expired") -> AssetRights:
        return self._set(rights_id, ApprovalStatus.EXPIRED, reason)

    def _set(
        self,
        rights_id: UUID,
        status: ApprovalStatus,
        reason: str,
    ) -> AssetRights:
        with unit_of_work(self.database) as uow:
            return uow.rights_state.transition(
                rights_id=rights_id,
                status=status,
                rejection_reason=reason,
            )
