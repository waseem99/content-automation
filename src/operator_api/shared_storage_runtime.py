from __future__ import annotations

import os
from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from src.application.shared_storage.models import (
    ArtifactVersionRequest,
    BackupPrepareRequest,
    DeletionRequest,
    LegalHoldRequest,
    RestoreVerifyRequest,
    SignedAccessRequest,
    StorageBackendRequest,
)
from src.application.shared_storage.providers import SharedStorageError
from src.application.shared_storage.runtime import SharedProviderRegistry
from src.application.shared_storage.service import SharedArtifactError, SharedArtifactService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_shared_storage_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
    providers: SharedProviderRegistry | None = None,
) -> None:
    if getattr(app.state, "shared_storage_routes_installed", False):
        return
    app.state.shared_storage_routes_installed = True
    service = (
        SharedArtifactService(
            database,
            providers=providers,
            public_base_url=os.getenv("SHARED_MEDIA_PUBLIC_BASE_URL", ""),
        )
        if database is not None
        else None
    )
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> SharedArtifactService:
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

    def artifact_brand_id(artifact_version_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                "SELECT brand_id FROM football_brief.shared_artifact_versions WHERE id=%s",
                (artifact_version_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="shared_artifact_not_found")
        return str(row["brand_id"])

    def grant_brand_id(grant_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                "SELECT brand_id FROM football_brief.shared_access_grants WHERE id=%s",
                (grant_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="access_grant_not_found")
        return str(row["brand_id"])

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except SharedArtifactError as exc:
            raise_shared_error(exc)
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

    @app.get("/storage/backends")
    def list_storage_backends(
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "ok": True,
            "operator": operator.operator_id,
            "backends": require_service().list_backends(),
        }

    @app.post("/storage/backends")
    def create_storage_backend(
        request: StorageBackendRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().create_backend(request=request, actor=operator.operator_id)),
        }

    @app.post("/storage/backends/{backend_id}/activate")
    def activate_storage_backend(
        backend_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().activate_backend(backend_id=backend_id, actor=operator.operator_id)),
        }

    @app.get("/storage/artifacts")
    def list_shared_artifacts(
        brand_id: UUID | None = Query(default=None),
        content_id: UUID | None = Query(default=None),
        include_history: bool = Query(default=True),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if content_id:
            scoped_brand = content_brand_id(content_id)
            require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=scoped_brand)
            brand_ids = [UUID(scoped_brand)]
        elif brand_id:
            require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id))
            brand_ids = [brand_id]
        elif operator.is_admin:
            require_access(operator, AccessPermission.READ_PORTFOLIO)
            brand_ids = None
        else:
            brand_ids = [UUID(item) for item in operator.brand_ids]
        artifacts = require_service().list_artifacts(
            brand_ids=brand_ids,
            content_id=content_id,
            include_history=include_history,
        )
        return {"ok": True, "operator": operator.operator_id, "artifacts": artifacts}

    @app.post("/storage/artifacts")
    def create_shared_artifact(
        request: ArtifactVersionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = str(request.brand_id)
        if request.portfolio_content_id:
            expected = content_brand_id(request.portfolio_content_id)
            if expected != brand_id:
                raise HTTPException(status_code=422, detail="content_brand_mismatch")
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().create_artifact_version(
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.get("/storage/artifacts/{artifact_version_id}")
    def shared_artifact_detail(
        artifact_version_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=artifact_brand_id(artifact_version_id),
        )
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().detail(artifact_version_id=artifact_version_id)),
        }

    @app.post("/storage/artifacts/{artifact_version_id}/access")
    def issue_shared_access(
        artifact_version_id: UUID,
        request: SignedAccessRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = artifact_brand_id(artifact_version_id)
        if request.access_purpose == "review":
            require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        elif operator.is_admin:
            require_access(operator, AccessPermission.READ_PORTFOLIO)
        elif OperatorRole.PRODUCER in operator.roles:
            require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        else:
            raise HTTPException(status_code=403, detail="shared_access_permission_denied")
        result = invoke(
            lambda: require_service().issue_access(
                artifact_version_id=artifact_version_id,
                request=request,
                actor=operator.operator_id,
            )
        )
        return {"ok": True, "operator": operator.operator_id, "access": result.model_dump(mode="json")}

    @app.post("/storage/access/{grant_id}/revoke")
    def revoke_shared_access(
        grant_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=grant_brand_id(grant_id),
        )
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().revoke_access(grant_id=grant_id, actor=operator.operator_id)),
        }

    @app.post("/storage/artifacts/{artifact_version_id}/legal-hold")
    def set_artifact_legal_hold(
        artifact_version_id: UUID,
        request: LegalHoldRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().set_legal_hold(
                    artifact_version_id=artifact_version_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/storage/artifacts/{artifact_version_id}/delete")
    def delete_shared_artifact(
        artifact_version_id: UUID,
        request: DeletionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().delete_artifact(
                    artifact_version_id=artifact_version_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/storage/backups")
    def prepare_shared_backup(
        request: BackupPrepareRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().prepare_backup(request=request, actor=operator.operator_id)),
        }

    @app.post("/storage/backups/{snapshot_id}/verify-restore")
    def verify_shared_restore(
        snapshot_id: UUID,
        request: RestoreVerifyRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().verify_restore(
                    snapshot_id=snapshot_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.get("/shared-media/{grant_id}", response_model=None)
    def shared_media_access(
        grant_id: UUID,
        token: str,
        request: Request,
    ) -> Response:
        try:
            target = require_service().consume_access(
                grant_id=grant_id,
                token=token,
                remote_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        except SharedArtifactError as exc:
            status_code = 410 if exc.code in {"access_grant_expired", "access_grant_revoked"} else 404
            if exc.code == "access_token_invalid":
                status_code = 403
            raise HTTPException(status_code=status_code, detail={"code": exc.code}) from exc
        except SharedStorageError as exc:
            raise HTTPException(status_code=404, detail={"code": "shared_object_unavailable"}) from exc
        if target.kind == "file":
            return FileResponse(
                target.value,
                media_type=target.mime_type,
                filename=target.filename,
                content_disposition_type="inline",
            )
        if target.kind == "redirect":
            return RedirectResponse(str(target.value), status_code=307)
        raise HTTPException(status_code=500, detail="unsupported_shared_access_target")


def raise_shared_error(exc: SharedArtifactError) -> None:
    if exc.code in {
        "shared_backend_not_found",
        "canonical_asset_not_found",
        "shared_artifact_not_found",
        "shared_artifact_role_not_available",
        "access_grant_not_found",
        "backup_snapshot_not_found",
        "restored_backend_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "artifact_parent_not_current",
        "artifact_parent_without_current",
        "shared_backend_not_activatable",
        "shared_backend_already_active",
        "access_grant_not_found_or_revoked",
        "backup_snapshot_not_prepared",
    }:
        status_code = 409
    elif exc.code == "operator_inactive_or_missing":
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, **exc.details},
    ) from exc
