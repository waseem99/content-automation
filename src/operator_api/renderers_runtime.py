from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.renderers.models import (
    RendererCatalogueCreate,
    RendererHealthUpdate,
    RendererOperation,
    RendererRepriceRequest,
    RendererResolveRequest,
    RendererStatus,
    RendererSubmissionRequest,
)
from src.application.renderers.service import RendererCatalogueError, RendererCatalogueService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class RendererRetireRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


def install_renderer_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "renderer_routes_installed", False):
        return
    app.state.renderer_routes_installed = True
    service = RendererCatalogueService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> RendererCatalogueService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    @app.get("/production/renderers")
    def list_renderers(
        operator: OperatorIdentity = Depends(authenticate),
        status: list[RendererStatus] = Query(default=[]),
        operation: list[RendererOperation] = Query(default=[]),
        renderer_key: str | None = Query(default=None, min_length=3, max_length=120),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        items = require_service().list_entries(
            statuses=[value.value for value in status],
            operations=[value.value for value in operation],
            renderer_key=renderer_key,
        )
        return {"ok": True, "operator": operator.operator_id, "count": len(items), "items": items}

    @app.post("/production/renderers/resolve")
    def resolve_renderer(
        request: RendererResolveRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().resolve(request)
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/renderers/simulate")
    def submit_simulated_renderer(
        request: RendererSubmissionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().submit_simulated(request, actor=operator.operator_id)
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/production/renderers/attempts/{attempt_id}")
    def get_renderer_attempt(
        attempt_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().attempt(attempt_id=attempt_id)
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/renderers")
    def create_renderer(
        request: RendererCatalogueCreate,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        try:
            result = require_service().create_draft(request, actor=operator.operator_id)
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/renderers/{renderer_id}/activate")
    def activate_renderer(
        renderer_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        try:
            result = require_service().activate(renderer_id=renderer_id, actor=operator.operator_id)
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/renderers/{renderer_id}/retire")
    def retire_renderer(
        renderer_id: UUID,
        request: RendererRetireRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        try:
            result = require_service().retire(
                renderer_id=renderer_id,
                actor=operator.operator_id,
                reason=request.reason,
            )
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/renderers/{renderer_id}/reprice")
    def reprice_renderer(
        renderer_id: UUID,
        request: RendererRepriceRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        try:
            result = require_service().reprice(
                renderer_id=renderer_id,
                request=request,
                actor=operator.operator_id,
            )
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/renderers/{renderer_id}/health")
    def update_renderer_health(
        renderer_id: UUID,
        request: RendererHealthUpdate,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        try:
            result = require_service().update_health(
                renderer_id=renderer_id,
                request=request,
                actor=operator.operator_id,
            )
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        return {"operator": operator.operator_id, **result}


def require_admin(operator: OperatorIdentity) -> None:
    if not operator.is_admin:
        raise HTTPException(status_code=403, detail="admin_required")
    require_access(operator, AccessPermission.MANAGE_BRANDS)


def raise_renderer_error(exc: RendererCatalogueError) -> None:
    status_code = 409
    if exc.code in {"renderer_not_found", "renderer_attempt_not_found"}:
        status_code = 404
    elif exc.code in {"operator_inactive_or_missing"}:
        status_code = 403
    elif exc.code in {
        "no_supported_renderer",
        "renderer_submission_not_supported",
        "renderer_adapter_not_configured",
    }:
        status_code = 422
    elif exc.code == "renderer_submission_failed":
        status_code = 502
    raise HTTPException(status_code=status_code, detail={"code": exc.code, **exc.details})
