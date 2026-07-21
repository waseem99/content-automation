from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException

from src.application.shared_storage.models import ExistingAssetMigrationRequest, StorageQuotaRequest
from src.application.shared_storage.providers import SharedStorageError
from src.application.shared_storage.runtime import SharedProviderRegistry
from src.application.shared_storage.service import SharedArtifactError
from src.application.shared_storage.validated_service import ValidatedSharedArtifactService
from src.infrastructure.database.connection import Database
from src.operator_api.access import AccessPermission, OperatorAccessService, OperatorIdentity, require_access
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_shared_storage_management_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
    providers: SharedProviderRegistry | None = None,
) -> None:
    if getattr(app.state, "shared_storage_management_routes_installed", False):
        return
    app.state.shared_storage_management_routes_installed = True
    service = (
        ValidatedSharedArtifactService(database, providers=providers)
        if database is not None
        else None
    )
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ValidatedSharedArtifactService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_admin(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except SharedArtifactError as exc:
            status = 404 if exc.code in {"shared_backend_not_found", "canonical_asset_not_found"} else 422
            raise HTTPException(status_code=status, detail={"code": exc.code, **exc.details}) from exc
        except SharedStorageError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "shared_storage_provider_error", "message": str(exc)[:500]},
            ) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "shared_storage_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.post("/storage/quotas")
    def configure_storage_quota(
        request: StorageQuotaRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().configure_quota(request=request, actor=operator.operator_id)),
        }

    @app.get("/storage/quotas/{backend_id}")
    def storage_quota_status(
        backend_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().quota_status(backend_id=backend_id)),
        }

    @app.post("/storage/migrate-assets")
    def migrate_existing_assets(
        request: ExistingAssetMigrationRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().migrate_existing_assets(
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }
