from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.pre_generation import PreGenerationError
from src.application.pre_generation.validated_service import ValidatedPreGenerationService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class RetryItemsRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=1000)


class ResolveExceptionGroupRequest(BaseModel):
    exception_code: str = Field(min_length=2, max_length=120)
    rule_version: str = Field(min_length=1, max_length=120)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    action: Literal["retry", "waive"]
    rationale: str = Field(min_length=5, max_length=5000)


def install_p120_pre_generation_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "p120_pre_generation_routes_installed", False):
        return
    app.state.p120_pre_generation_routes_installed = True
    service = ValidatedPreGenerationService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ValidatedPreGenerationService:
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

    @app.post("/p120/campaigns/{campaign_id}/autopilot/start")
    def start_autopilot(
        campaign_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().ensure_runs(
                campaign_id=campaign_id,
                actor=operator.operator_id,
            )
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p120/campaigns/{campaign_id}/dashboard")
    def campaign_dashboard(
        campaign_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().dashboard(campaign_id=campaign_id)
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p120/campaigns/{campaign_id}/items")
    def campaign_grid(
        campaign_id: UUID,
        state: str | None = Query(default=None, max_length=80),
        exception_code: str | None = Query(default=None, max_length=120),
        after_ordinal: int | None = Query(default=None, ge=0),
        limit: int = Query(default=200, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().grid(
                campaign_id=campaign_id,
                state=state,
                exception_code=exception_code,
                after_ordinal=after_ordinal,
                limit=limit,
            )
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p120/campaigns/{campaign_id}/exception-groups")
    def exception_groups(
        campaign_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            groups = require_service().exception_groups(campaign_id=campaign_id)
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {
            "ok": True,
            "kind": "pre_generation_exception_groups",
            "operator": operator.operator_id,
            "groups": groups,
        }

    @app.post("/p120/campaigns/{campaign_id}/exceptions/resolve")
    def resolve_exception_group(
        campaign_id: UUID,
        request: ResolveExceptionGroupRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().resolve_exception_group(
                campaign_id=campaign_id,
                exception_code=request.exception_code,
                rule_version=request.rule_version,
                fingerprint=request.fingerprint,
                action=request.action,
                rationale=request.rationale,
                actor=operator.operator_id,
            )
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p120/campaigns/{campaign_id}/items/retry")
    def retry_items(
        campaign_id: UUID,
        request: RetryItemsRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().retry_items(
                campaign_id=campaign_id,
                item_ids=request.item_ids,
                actor=operator.operator_id,
            )
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p120/campaigns/{campaign_id}/pause")
    def pause_campaign(
        campaign_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().set_campaign_status(
                campaign_id=campaign_id,
                status="paused",
                actor=operator.operator_id,
            )
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p120/campaigns/{campaign_id}/resume")
    def resume_campaign(
        campaign_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().set_campaign_status(
                campaign_id=campaign_id,
                status="active",
                actor=operator.operator_id,
            )
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p120/campaigns/{campaign_id}/items/{item_id}/package")
    def item_package(
        campaign_id: UUID,
        item_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().package_for_item(
                campaign_id=campaign_id,
                item_id=item_id,
            )
        except PreGenerationError as exc:
            raise_pre_generation_error(exc)
        return {"operator": operator.operator_id, **result}


def raise_pre_generation_error(exc: PreGenerationError) -> None:
    if exc.code in {
        "campaign_not_found",
        "pre_generation_run_not_found",
        "exception_group_not_found",
        "ready_pre_generation_package_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "only_active_campaign_can_be_paused",
        "only_paused_campaign_can_be_resumed",
        "hard_block_cannot_be_waived",
        "pre_generation_lease_lost",
    }:
        status_code = 409
    elif exc.code == "operator_inactive_or_missing":
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(status_code=status_code, detail={"code": exc.code, **exc.details}) from exc


__all__ = ["install_p120_pre_generation_routes"]
