from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.renderers.models import (
    RendererCapabilityRequest,
    RendererEntryRequest,
    RendererHealthRequest,
    RendererOperation,
    RendererRepriceRequest,
    RendererStatus,
    SimulatedJobRequest,
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

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def content_brand_id(content_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="content_not_found")
        return str(row["brand_id"])

    def invoke(call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return call()
        except RendererCatalogueError as exc:
            raise_renderer_error(exc)
        except psycopg.Error as exc:
            message = str(exc).splitlines()[0][:500]
            raise HTTPException(
                status_code=422,
                detail={"code": "renderer_catalogue_integrity_violation", "message": message},
            ) from exc

    @app.get("/renderers/catalogue")
    def renderer_catalogue(
        status: list[RendererStatus] = Query(default=[]),
        operation: list[RendererOperation] = Query(default=[]),
        provider_key: str | None = Query(default=None, max_length=100),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        entries = require_service().list_entries(
            statuses=[item.value for item in status],
            operations=[item.value for item in operation],
            provider_key=provider_key,
        )
        return {"ok": True, "operator": operator.operator_id, "entries": entries}

    @app.get("/renderers/catalogue/{entry_id}")
    def renderer_detail(
        entry_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().detail(entry_id=entry_id))}

    @app.post("/renderers/catalogue")
    def create_renderer_entry(
        request: RendererEntryRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().create_entry(request=request, actor=operator.operator_id)),
        }

    @app.post("/renderers/catalogue/{entry_id}/activate")
    def activate_renderer_entry(
        entry_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().activate(entry_id=entry_id, actor=operator.operator_id)),
        }

    @app.post("/renderers/catalogue/{entry_id}/retire")
    def retire_renderer_entry(
        entry_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().retire(entry_id=entry_id, actor=operator.operator_id)),
        }

    @app.post("/renderers/catalogue/{entry_id}/reprice")
    def reprice_renderer_entry(
        entry_id: UUID,
        request: RendererRepriceRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().reprice(
                    entry_id=entry_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/renderers/catalogue/{entry_id}/health")
    def record_renderer_health(
        entry_id: UUID,
        request: RendererHealthRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().observe_health(
                    entry_id=entry_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/renderers/preflight")
    def renderer_preflight(
        request: RendererCapabilityRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=content_brand_id(request.portfolio_content_id),
        )
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().preflight(request=request, actor=operator.operator_id)),
        }

    @app.post("/renderers/simulated-jobs")
    def enqueue_simulated_renderer_job(
        request: SimulatedJobRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT rp.portfolio_content_id
                   FROM football_brief.renderer_preflight_records rp
                   WHERE rp.id=%s""",
                (request.renderer_preflight_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="renderer_preflight_not_found")
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=content_brand_id(row["portfolio_content_id"]),
        )
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().enqueue_simulated(
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }


def raise_renderer_error(exc: RendererCatalogueError) -> None:
    if exc.code in {
        "renderer_entry_not_found",
        "renderer_parent_not_found",
        "renderer_preflight_not_found",
        "content_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "content_version_conflict",
        "renderer_parent_required",
        "renderer_entry_not_draft",
        "renderer_entry_not_active",
        "renderer_not_available",
    }:
        status_code = 409
    elif exc.code in {
        "operator_inactive_or_missing",
        "paid_renderer_execution_disabled",
    }:
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, **exc.details},
    ) from exc
