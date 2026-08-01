from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.campaign_storage import CampaignStorageError, CampaignStorageService
from src.infrastructure.database.connection import Database
from src.operator_api.access import OperatorAccessService, OperatorIdentity
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class RegisterLocalLocationRequest(BaseModel):
    path: str = Field(min_length=3, max_length=4000)


class UploadDriveLocationRequest(BaseModel):
    source_path: str | None = Field(default=None, min_length=3, max_length=4000)
    parent_folder_id: str | None = Field(default=None, min_length=3, max_length=300)


class ReconcileStorageRequest(BaseModel):
    provider: Literal["local", "google_drive"] | None = None
    strict_drive_download: bool = False
    limit: int = Field(default=1000, ge=1, le=10000)


def install_p120_storage_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "p120_storage_routes_installed", False):
        return
    app.state.p120_storage_routes_installed = True
    service = CampaignStorageService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> CampaignStorageService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_admin(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")

    @app.get("/p120/assets/{asset_id}/locations")
    def locations(
        asset_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.active:
            raise HTTPException(status_code=403, detail="operator_inactive")
        try:
            result = require_service().locations(asset_id=asset_id)
        except CampaignStorageError as exc:
            raise_storage_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/p120/assets/{asset_id}/locations/local")
    def register_local(
        asset_id: UUID,
        request: RegisterLocalLocationRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        try:
            result = require_service().register_local(
                asset_id=asset_id,
                path=Path(request.path),
                actor=operator.operator_id,
            )
        except CampaignStorageError as exc:
            raise_storage_error(exc)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="local_file_not_found") from exc
        return {"operator": operator.operator_id, **result}

    @app.post("/p120/assets/{asset_id}/locations/google-drive")
    def upload_drive(
        asset_id: UUID,
        request: UploadDriveLocationRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        try:
            result = require_service().upload_google_drive(
                asset_id=asset_id,
                actor=operator.operator_id,
                source_path=Path(request.source_path) if request.source_path else None,
                parent_folder_id=request.parent_folder_id,
            )
        except CampaignStorageError as exc:
            raise_storage_error(exc)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="local_file_not_found") from exc
        return {"operator": operator.operator_id, **result}

    @app.post("/p120/storage/reconcile")
    def reconcile(
        request: ReconcileStorageRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        try:
            result = require_service().reconcile(
                actor=operator.operator_id,
                provider=request.provider,
                strict_drive_download=request.strict_drive_download,
                limit=request.limit,
            )
        except CampaignStorageError as exc:
            raise_storage_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/p120/storage/reconciliation-runs")
    def reconciliation_runs(
        limit: int = Query(default=50, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM football_brief.asset_storage_reconciliation_runs
                   ORDER BY created_at DESC,id DESC LIMIT %s""",
                (limit,),
            ).fetchall()
        return {
            "ok": True,
            "kind": "asset_storage_reconciliation_runs",
            "operator": operator.operator_id,
            "runs": [dict(row) for row in rows],
        }


def raise_storage_error(exc: CampaignStorageError) -> None:
    if exc.code == "asset_not_found":
        status_code = 404
    elif exc.code in {
        "operator_inactive_or_missing",
        "local_path_outside_allowed_roots",
    }:
        status_code = 403
    elif exc.code in {
        "google_drive_upload_failed",
        "google_drive_reconciliation_failed",
    }:
        status_code = 502
    elif exc.code == "google_drive_not_configured":
        status_code = 503
    else:
        status_code = 422
    raise HTTPException(status_code=status_code, detail={"code": exc.code, **exc.details}) from exc


__all__ = ["install_p120_storage_routes"]
