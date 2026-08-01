from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.campaigns import (
    AutopilotPolicyCreateRequest,
    CampaignCreateRequest,
    CampaignError,
    CampaignItemsAddRequest,
    CampaignService,
)
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
    visible_brand_ids,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_p119_campaign_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "p119_campaign_routes_installed", False):
        return
    app.state.p119_campaign_routes_installed = True
    service = CampaignService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> CampaignService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def campaign_brand_id(campaign_id: UUID) -> str:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                "SELECT brand_id FROM football_brief.production_campaigns WHERE id=%s",
                (campaign_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="campaign_not_found")
        return str(row["brand_id"])

    def version_brand_id(campaign_version_id: UUID) -> str:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                """SELECT c.brand_id
                   FROM football_brief.production_campaign_versions v
                   JOIN football_brief.production_campaigns c ON c.id=v.campaign_id
                   WHERE v.id=%s""",
                (campaign_version_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="campaign_version_not_found")
        return str(row["brand_id"])

    @app.post("/p119/campaigns")
    def create_campaign(
        request: CampaignCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=str(request.brand_id))
        try:
            result = require_service().create_campaign(request, actor=operator.operator_id)
        except CampaignError as exc:
            raise_campaign_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p119/campaigns")
    def list_campaigns(
        limit: int = Query(default=100, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        scoped = visible_brand_ids(operator)
        brand_ids = None if scoped is None else [UUID(value) for value in scoped]
        try:
            campaigns = require_service().list_campaigns(brand_ids=brand_ids, limit=limit)
        except CampaignError as exc:
            raise_campaign_error(exc)
        return {
            "ok": True,
            "kind": "p119_campaign_list",
            "operator": operator.operator_id,
            "campaigns": campaigns,
        }

    @app.get("/p119/campaigns/{campaign_id}")
    def campaign_detail(
        campaign_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().detail(campaign_id)
        except CampaignError as exc:
            raise_campaign_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p119/campaign-versions/{campaign_version_id}/items")
    def add_campaign_items(
        campaign_version_id: UUID,
        request: CampaignItemsAddRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=version_brand_id(campaign_version_id),
        )
        try:
            result = require_service().add_items(
                campaign_version_id=campaign_version_id,
                request=request,
                actor=operator.operator_id,
            )
        except CampaignError as exc:
            raise_campaign_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p119/campaign-versions/{campaign_version_id}/validate")
    def validate_campaign_version(
        campaign_version_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=version_brand_id(campaign_version_id),
        )
        try:
            result = require_service().validate_version(
                campaign_version_id=campaign_version_id,
                actor=operator.operator_id,
            )
        except CampaignError as exc:
            raise_campaign_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p119/campaign-versions/{campaign_version_id}/activate")
    def activate_campaign_version(
        campaign_version_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=version_brand_id(campaign_version_id),
        )
        try:
            result = require_service().activate_version(
                campaign_version_id=campaign_version_id,
                actor=operator.operator_id,
            )
        except CampaignError as exc:
            raise_campaign_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p119/brands/{brand_id}/autopilot-policy")
    def get_autopilot_policy(
        brand_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id))
        try:
            result = require_service().policy(brand_id=brand_id)
        except CampaignError as exc:
            raise_campaign_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p119/brands/{brand_id}/autopilot-policy")
    def create_autopilot_policy(
        brand_id: UUID,
        request: AutopilotPolicyCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        try:
            result = require_service().create_policy(
                brand_id=brand_id,
                request=request,
                actor=operator.operator_id,
            )
        except CampaignError as exc:
            raise_campaign_error(exc)
        return {"operator": operator.operator_id, **result}


def raise_campaign_error(exc: CampaignError) -> None:
    if exc.code in {
        "campaign_not_found",
        "campaign_version_not_found",
        "active_autopilot_policy_not_found",
        "brand_not_found_or_inactive",
    }:
        status_code = 404
    elif exc.code in {
        "campaign_key_brand_conflict",
        "campaign_version_not_editable",
        "campaign_version_not_validatable",
        "validated_campaign_version_required",
        "all_campaign_items_must_be_valid",
    }:
        status_code = 409
    elif exc.code == "operator_inactive_or_missing":
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(status_code=status_code, detail={"code": exc.code, **exc.details}) from exc


__all__ = ["install_p119_campaign_routes"]
