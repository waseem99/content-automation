from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.infrastructure.database.connection import Database
from src.operations.always_on_pipeline import AlwaysOnLocalPipelineService
from src.operations.local_pipeline import LocalPipelineError
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
    visible_brand_ids,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class LocalBatchRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)
    brand_id: UUID | None = None


class ContinueApprovedRequest(LocalBatchRequest):
    include_audio: bool = True
    include_visuals: bool = True
    include_previews: bool = True


def install_local_pipeline_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "local_pipeline_routes_installed", False):
        return
    app.state.local_pipeline_routes_installed = True
    service = AlwaysOnLocalPipelineService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> AlwaysOnLocalPipelineService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def scope(operator: OperatorIdentity, brand_id: UUID | None, permission: AccessPermission) -> list[UUID] | None:
        if brand_id is not None:
            require_access(operator, permission, brand_id=str(brand_id))
            return [brand_id]
        require_access(operator, permission)
        visible = visible_brand_ids(operator)
        return None if visible is None else [UUID(value) for value in sorted(visible)]

    @app.get("/local-production/status")
    def local_status(operator: OperatorIdentity = Depends(authenticate)) -> dict[str, Any]:
        return {
            "operator": operator.operator_id,
            **require_service().status(
                brand_ids=scope(operator, None, AccessPermission.READ_PORTFOLIO)
            ),
        }

    @app.post("/local-production/enqueue-scripts")
    def enqueue_scripts(
        request: LocalBatchRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        try:
            result = require_service().enqueue_scripts(
                limit=request.limit,
                actor=operator.operator_id,
                brand_ids=scope(operator, request.brand_id, AccessPermission.RUN_PRODUCTION),
            )
        except LocalPipelineError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "details": exc.details}) from exc
        return {"operator": operator.operator_id, **result}

    @app.post("/local-production/continue-approved")
    def continue_approved(
        request: ContinueApprovedRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        try:
            result = require_service().continue_approved(
                limit=request.limit,
                actor=operator.operator_id,
                brand_ids=scope(operator, request.brand_id, AccessPermission.RUN_PRODUCTION),
                include_audio=request.include_audio,
                include_visuals=request.include_visuals,
                include_previews=request.include_previews,
            )
        except LocalPipelineError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "details": exc.details}) from exc
        return {"operator": operator.operator_id, **result}
