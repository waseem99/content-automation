from __future__ import annotations

from typing import Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException

from src.infrastructure.database.connection import Database
from src.operations.models import OperationsEnvironment
from src.operations.service import OperationsError
from src.operations.settings import OperationsSettings
from src.operations.validated_service import ValidatedOperationsService
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_operations_monitoring_route(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
    operations_settings: OperationsSettings,
) -> None:
    """Install the read-only monitoring snapshot used by Creator Studio.

    The existing POST `/operations/monitor/check` also records alert evidence.
    Merely opening the Operations workspace must not create or mutate alerts, so
    Creator Studio receives a separate authenticated GET snapshot.
    """

    if getattr(app.state, "p135_operations_monitoring_route_installed", False):
        return
    app.state.p135_operations_monitoring_route_installed = True

    service = ValidatedOperationsService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    @app.get("/operations/monitoring")
    def operations_monitoring(
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        if database is None or service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")

        environment = OperationsEnvironment(operations_settings.environment)
        health = database.health_check(operations_settings.migrations_dir)
        api_healthy = bool(
            health.database_reachable
            and health.schema_present
            and health.migrations_table_present
        )
        try:
            snapshot = service.snapshot(
                environment=environment,
                api_healthy=api_healthy,
                storage_capacity_bytes=operations_settings.storage_capacity_bytes,
            )
        except OperationsError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, **exc.details},
            ) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "operations_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

        return {
            "ok": api_healthy,
            "kind": "operations_monitoring_snapshot",
            "operator": operator.operator_id,
            "environment": environment.value,
            "snapshot": snapshot,
            "read_only": True,
        }


__all__ = ["install_operations_monitoring_route"]
