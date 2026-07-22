from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException

from src.application.acceptance.controlled_start_models import (
    PilotControlledStartRequest,
)
from src.application.acceptance.controlled_start_service import (
    ControlledPilotStartService,
)
from src.application.acceptance.service import AcceptancePilotError
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_acceptance_controlled_start_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "acceptance_controlled_start_routes_installed", False):
        return
    app.state.acceptance_controlled_start_routes_installed = True
    service = ControlledPilotStartService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ControlledPilotStartService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_admin(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)

    def require_read_scope(operator: OperatorIdentity, pilot_id: UUID) -> None:
        if not operator.is_admin and not operator.roles.intersection(
            {OperatorRole.REVIEWER, OperatorRole.PUBLISHER}
        ):
            raise HTTPException(status_code=403, detail="acceptance_read_role_required")
        brand_ids = set(require_service().pilot_brand_ids(pilot_id=pilot_id))
        if not operator.is_admin and not brand_ids.issubset(set(operator.brand_ids)):
            raise HTTPException(status_code=403, detail="pilot_brand_scope_required")

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except AcceptancePilotError as exc:
            status = 422
            if exc.code == "pilot_not_found":
                status = 404
            elif exc.code == "pilot_role_required":
                status = 403
            elif exc.code in {
                "pilot_controlled_start_replay_mismatch",
                "pilot_start_duplicate_binding",
            }:
                status = 409
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code, **exc.details},
            ) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "acceptance_controlled_start_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.get("/acceptance/pilots/{pilot_id}/start-readiness")
    def controlled_start_readiness(
        pilot_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        invoke(lambda: require_read_scope(operator, pilot_id))
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().start_readiness(pilot_id=pilot_id)
            ),
        }

    @app.post("/acceptance/pilots/{pilot_id}/start-controlled")
    def controlled_start(
        pilot_id: UUID,
        request: PilotControlledStartRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().start_controlled(
                    pilot_id=pilot_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }


__all__ = ["install_acceptance_controlled_start_routes"]
