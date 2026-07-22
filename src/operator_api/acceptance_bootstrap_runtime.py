from __future__ import annotations

from typing import Any, Callable

import psycopg
from fastapi import Depends, FastAPI, HTTPException

from src.application.acceptance.bootstrap_models import PilotBootstrapRequest
from src.application.acceptance.bootstrap_service import AcceptanceBootstrapService
from src.application.acceptance.service import AcceptancePilotError
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_acceptance_bootstrap_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "acceptance_bootstrap_routes_installed", False):
        return
    app.state.acceptance_bootstrap_routes_installed = True
    service = AcceptanceBootstrapService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> AcceptanceBootstrapService:
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
        except AcceptancePilotError as exc:
            status = 422
            if exc.code == "pilot_bootstrap_content_not_found":
                status = 404
            elif exc.code in {
                "pilot_bootstrap_key_conflict",
                "pilot_bootstrap_replay_mismatch",
                "pilot_bootstrap_content_already_bound",
            }:
                status = 409
            elif exc.code == "pilot_role_required":
                status = 403
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code, **exc.details},
            ) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "acceptance_bootstrap_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.post("/acceptance/pilots/bootstrap-draft")
    def bootstrap_draft_pilot(
        request: PilotBootstrapRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().bootstrap(
                    request,
                    actor=operator.operator_id,
                )
            ),
        }


__all__ = ["install_acceptance_bootstrap_routes"]
