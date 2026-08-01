from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.pre_generation.query_service import CampaignQueryService, SORTS
from src.application.pre_generation.service import PreGenerationError
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class RetryMatchingRequest(BaseModel):
    query: str | None = Field(default=None, max_length=500)
    states: list[str] = Field(default_factory=list, max_length=20)
    exception_codes: list[str] = Field(default_factory=list, max_length=20)
    maximum: int = Field(default=20_000, ge=1, le=20_000)


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def install_p121_campaign_grid_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "p121_campaign_grid_routes_installed", False):
        return
    app.state.p121_campaign_grid_routes_installed = True
    service = CampaignQueryService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> CampaignQueryService:
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

    @app.get("/p121/campaigns/{campaign_id}/items")
    def query_items(
        campaign_id: UUID,
        q: str | None = Query(default=None, max_length=500),
        states: str | None = Query(default=None, max_length=500),
        exceptions: str | None = Query(default=None, max_length=1000),
        sort: str = Query(default="ordinal"),
        direction: str = Query(default="asc", pattern=r"^(asc|desc)$"),
        cursor: str | None = Query(default=None, max_length=2000),
        limit: int = Query(default=250, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=campaign_brand_id(campaign_id),
        )
        if sort not in SORTS:
            raise HTTPException(status_code=422, detail={"code": "unsupported_campaign_sort"})
        try:
            result = require_service().query_items(
                campaign_id=campaign_id,
                query=q,
                states=_split(states),
                exception_codes=_split(exceptions),
                sort=sort,
                direction=direction,
                cursor=cursor,
                limit=limit,
            )
        except PreGenerationError as exc:
            raise_grid_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p121/campaigns/{campaign_id}/retry-matching")
    def retry_matching(
        campaign_id: UUID,
        request: RetryMatchingRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=campaign_brand_id(campaign_id),
        )
        try:
            result = require_service().retry_matching(
                campaign_id=campaign_id,
                query=request.query,
                states=request.states,
                exception_codes=request.exception_codes,
                actor=operator.operator_id,
                maximum=request.maximum,
            )
        except PreGenerationError as exc:
            raise_grid_error(exc)
        return {"operator": operator.operator_id, **result}


def raise_grid_error(exc: PreGenerationError) -> None:
    if exc.code == "campaign_not_found":
        status_code = 404
    elif exc.code in {
        "campaign_cursor_sort_mismatch",
        "bulk_retry_selection_exceeds_maximum",
    }:
        status_code = 409
    elif exc.code == "operator_inactive_or_missing":
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(status_code=status_code, detail={"code": exc.code, **exc.details}) from exc


__all__ = ["install_p121_campaign_grid_routes"]
