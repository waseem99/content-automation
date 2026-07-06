from __future__ import annotations

from uuid import UUID

from src.application.media.models import MediaAssetUseRequest
from src.application.media.policy_errors import MediaAssetPolicyFailure
from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint, RightsPlatform
from src.application.rights.gate import RightsGateService
from src.application.rights.request_models import RightsGateRequest
from src.domain.asset_enums import AssetType
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


_ROLE_TYPES = {
    "music": AssetType.AUDIO,
    "font": AssetType.FONT,
}


class MediaAssetPolicyService:
    def __init__(self, database: Database, rights_gate: RightsGateService) -> None:
        self.database = database
        self.rights_gate = rights_gate

    def authorize(self, request: MediaAssetUseRequest):
        expected_type = _ROLE_TYPES.get(request.role.strip().lower())
        if expected_type is None:
            raise MediaAssetPolicyFailure("Unsupported media policy role")

        self._verify_asset_types(request.asset_ids, expected_type)
        decision = self.rights_gate.evaluate(
            RightsGateRequest(
                workflow_run_id=request.workflow_run_id,
                gate_point=RightsGatePoint.MANIFEST_ADMISSION,
                asset_ids=request.asset_ids,
                platform=RightsPlatform(request.platform.strip().lower()),
                territory=request.territory,
                campaign=request.campaign,
                commercial_use=request.commercial_use,
                editorial_use=request.editorial_use,
                modification=request.modification,
                synthetic_edit=request.synthetic_edit,
                evaluated_by=request.evaluated_by,
            )
        )
        if decision.outcome != RightsDecisionOutcome.PASS:
            raise MediaAssetPolicyFailure(
                f"{request.role} assets are not approved for {request.platform}: "
                + ",".join(code.value for code in decision.reason_codes)
            )
        return decision

    def _verify_asset_types(self, asset_ids: tuple[UUID, ...], expected_type: AssetType) -> None:
        with unit_of_work(self.database) as uow:
            for asset_id in asset_ids:
                asset = uow.assets.get(asset_id)
                if asset.asset_type != expected_type:
                    raise MediaAssetPolicyFailure("Media asset type does not match role")
