from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.application.rights.exceptions import RightsApprovalError
from src.application.rights.reason_codes import RightsReasonCode
from src.domain.asset_status import ApprovalStatus, AssetLifecycleStatus
from src.domain.rights_models import AssetRights, AssetRightsCreate
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_rights_links import AssetRightsEvidenceLinkRepository
from src.infrastructure.database.repository_rights_state import RightsStateRepository
from src.infrastructure.database.uow import unit_of_work


class RightsApprovalService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_pending(self, data: AssetRightsCreate) -> AssetRights:
        if data.approval_status != ApprovalStatus.PENDING:
            raise RightsApprovalError(
                RightsReasonCode.RIGHTS_NOT_APPROVED,
                "New rights records must start pending",
            )
        with unit_of_work(self.database) as uow:
            asset = uow.assets.get_optional(data.asset_id)
            if asset is None or asset.lifecycle_status == AssetLifecycleStatus.DELETED:
                raise RightsApprovalError(
                    RightsReasonCode.ASSET_UNAVAILABLE,
                    "Rights require an available asset",
                )
            return uow.asset_rights.create(data)

    def link_evidence(
        self,
        *,
        rights_id: UUID,
        evidence_id: UUID,
        evidence_role: str,
        linked_by: str,
    ) -> dict:
        with unit_of_work(self.database) as uow:
            RightsStateRepository(uow.conn).get(rights_id)
            uow.rights_evidence.get(evidence_id)
            return AssetRightsEvidenceLinkRepository(uow.conn).create(
                asset_rights_id=rights_id,
                rights_evidence_id=evidence_id,
                evidence_role=evidence_role,
                linked_by=linked_by,
            )

    def approve(
        self,
        *,
        rights_id: UUID,
        approved_by: str,
        approved_at: datetime | None = None,
    ) -> AssetRights:
        at = approved_at or datetime.now(timezone.utc)
        with unit_of_work(self.database) as uow:
            state = RightsStateRepository(uow.conn)
            links = AssetRightsEvidenceLinkRepository(uow.conn)
            rights = state.get(rights_id)
            if links.count_for_rights(rights_id) < 1:
                raise RightsApprovalError(
                    RightsReasonCode.RIGHTS_EVIDENCE_MISSING,
                    "Approved rights require linked evidence",
                )
            if rights.attribution_required and not (rights.attribution_text or "").strip():
                raise RightsApprovalError(
                    RightsReasonCode.ATTRIBUTION_MISSING,
                    "Attribution text is required",
                )
            if rights.valid_from and rights.expires_at and rights.expires_at <= rights.valid_from:
                raise RightsApprovalError(
                    RightsReasonCode.RIGHTS_EXPIRED,
                    "Rights expiry must follow the valid-from timestamp",
                )
            return state.transition(
                rights_id=rights_id,
                status=ApprovalStatus.APPROVED,
                approved_by=approved_by,
                approved_at=at,
            )
