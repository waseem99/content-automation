from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException

from src.application.local_video.models import LocalVideoEnqueueRequest
from src.application.local_video.service import LocalVideoError, LocalVideoService
from src.infrastructure.database.connection import Database
from src.operator_api.access import AccessPermission, OperatorAccessService, OperatorIdentity, require_access
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_local_video_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "local_video_routes_installed", False):
        return
    app.state.local_video_routes_installed = True
    service = LocalVideoService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> LocalVideoService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def content_brand_id(content_id: UUID) -> str:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="content_not_found")
        return str(row["brand_id"])

    @app.get("/local-video/profiles")
    def profiles(operator: OperatorIdentity = Depends(authenticate)) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        return {"operator": operator.operator_id, **require_service().profiles()}

    @app.post("/local-video/preflight")
    def preflight(
        request: LocalVideoEnqueueRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=content_brand_id(request.portfolio_content_id),
        )
        try:
            result = require_service().preflight(request)
        except LocalVideoError as exc:
            raise_local_video_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/local-video/jobs")
    def enqueue(
        request: LocalVideoEnqueueRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=content_brand_id(request.portfolio_content_id),
        )
        try:
            result = require_service().enqueue(request, actor=operator.operator_id)
        except LocalVideoError as exc:
            raise_local_video_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/local-video/jobs/{job_id}")
    def detail(
        job_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        try:
            result = require_service().detail(job_id)
        except LocalVideoError as exc:
            raise_local_video_error(exc)
        brand_id = str(result["job"]["brand_id"])
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=brand_id)
        return {"operator": operator.operator_id, **result}


def raise_local_video_error(exc: LocalVideoError) -> None:
    if exc.code.endswith("_not_found") or exc.code in {"content_not_found"}:
        status = 404
    elif exc.code in {
        "content_version_conflict",
        "local_video_idempotency_binding_conflict",
    }:
        status = 409
    elif exc.code in {
        "local_video_preflight_rejected",
        "local_video_renderer_not_active",
        "local_video_model_policy_not_active",
        "local_video_catalogue_entry_not_active",
        "local_video_input_asset_not_eligible",
    }:
        status = 403
    else:
        status = 422
    raise HTTPException(status_code=status, detail={"code": exc.code, **exc.details}) from exc


__all__ = ["install_local_video_routes"]
