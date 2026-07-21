from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from src.infrastructure.database.connection import Database
from src.operations.models import (
    BackupSetRequest,
    DrillCompleteRequest,
    DrillStartRequest,
    MonitorThresholds,
    OperationsEnvironment,
    OperationsReleaseStatus,
    ReleaseRecordRequest,
    RestoreEvidenceRequest,
)
from src.operations.service import OperationsError, OperationsService
from src.operations.settings import OperationsSettings
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_operations_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
    operations_settings: OperationsSettings,
) -> None:
    if getattr(app.state, "operations_routes_installed", False):
        return
    app.state.operations_routes_installed = True
    service = OperationsService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> OperationsService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def require_admin(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except OperationsError as exc:
            status = 409
            if exc.code in {
                "operations_release_not_found",
                "operations_drill_not_running",
                "operations_alert_not_open",
                "operations_alert_not_resolvable",
            }:
                status = 404
            elif exc.code == "operations_admin_required":
                status = 403
            elif exc.code in {
                "storage_capacity_bytes_must_be_positive",
                "unsupported_release_transition_target",
            }:
                status = 422
            raise HTTPException(status_code=status, detail={"code": exc.code, **exc.details}) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "operations_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.get("/operations/config")
    def operations_config(
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "ok": True,
            "operator": operator.operator_id,
            "operations": operations_settings.public_snapshot(),
        }

    @app.post("/operations/releases")
    def record_operations_release(
        request: ReleaseRecordRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().record_release(request, actor=operator.operator_id)),
        }

    @app.post("/operations/releases/{release_id}/transition/{status}")
    def transition_operations_release(
        release_id: UUID,
        status: OperationsReleaseStatus,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().transition_release(
                    release_id=release_id,
                    status=status,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/operations/backups")
    def register_operations_backup(
        request: BackupSetRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().register_backup(request, actor=operator.operator_id)),
        }

    @app.post("/operations/restores")
    def record_operations_restore(
        request: RestoreEvidenceRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().record_restore(request, actor=operator.operator_id)),
        }

    @app.post("/operations/drills")
    def start_operations_drill(
        request: DrillStartRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().start_drill(request, actor=operator.operator_id)),
        }

    @app.post("/operations/drills/{drill_id}/complete")
    def complete_operations_drill(
        drill_id: UUID,
        request: DrillCompleteRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().complete_drill(
                    drill_id=drill_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.get("/operations/drills")
    def list_operations_drills(
        environment: OperationsEnvironment | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "ok": True,
            "operator": operator.operator_id,
            "items": invoke(
                lambda: require_service().list_drills(
                    environment=environment,
                    limit=limit,
                )
            ),
        }

    @app.post("/operations/monitor/check")
    def check_operations_monitoring(
        environment: OperationsEnvironment,
        thresholds: MonitorThresholds | None = None,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        health = require_database().health_check(operations_settings.migration_head.rsplit("/", 1)[0] or "migrations")
        api_healthy = bool(health.database_reachable and health.schema_present and health.migrations_table_present)
        snapshot = invoke(
            lambda: require_service().snapshot(
                environment=environment,
                api_healthy=api_healthy,
                storage_capacity_bytes=operations_settings.storage_capacity_bytes,
                thresholds=thresholds,
            )
        )
        alerts = invoke(
            lambda: require_service().detect_alerts(
                environment=environment,
                snapshot=snapshot,
                actor=operator.operator_id,
            )
        )
        return {
            "ok": not any(item["severity"] == "critical" for item in alerts),
            "operator": operator.operator_id,
            "snapshot": snapshot,
            "alerts": alerts,
        }

    @app.get("/operations/alerts")
    def list_operations_alerts(
        environment: OperationsEnvironment | None = Query(default=None),
        include_resolved: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        with require_database().connection() as conn:
            rows = conn.execute(
                """SELECT * FROM football_brief.operations_alert_events
                   WHERE (%s::text IS NULL OR environment=%s)
                     AND (%s OR status<>'resolved')
                   ORDER BY detected_at DESC,id DESC LIMIT %s""",
                (
                    environment.value if environment else None,
                    environment.value if environment else None,
                    include_resolved,
                    limit,
                ),
            ).fetchall()
        return {
            "ok": True,
            "operator": operator.operator_id,
            "items": [dict(row) for row in rows],
        }

    @app.post("/operations/alerts/{alert_id}/acknowledge")
    def acknowledge_operations_alert(
        alert_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().acknowledge_alert(
                    alert_id=alert_id,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/operations/alerts/{alert_id}/resolve")
    def resolve_operations_alert(
        alert_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().resolve_alert(
                    alert_id=alert_id,
                    actor=operator.operator_id,
                )
            ),
        }
