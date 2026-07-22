from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException

from src.application.acceptance.models import PilotRetireRequest
from src.application.acceptance.validated_service import ValidatedAcceptancePilotService
from src.infrastructure.database.connection import Database
from src.operator_api.access import AccessPermission, OperatorAccessService, OperatorIdentity, require_access
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_acceptance_revision_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "acceptance_revision_routes_installed", False):
        return
    app.state.acceptance_revision_routes_installed = True
    service = ValidatedAcceptancePilotService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ValidatedAcceptancePilotService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    @app.post("/acceptance/pilots/{pilot_id}/retire")
    def retire_pilot(
        pilot_id: UUID,
        request: PilotRetireRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        try:
            result = require_service().retire(
                pilot_id=pilot_id,
                request=request,
                actor=operator.operator_id,
            )
        except Exception as exc:
            from src.application.acceptance.service import AcceptancePilotError

            if isinstance(exc, AcceptancePilotError):
                raise HTTPException(
                    status_code=422,
                    detail={"code": exc.code, **exc.details},
                ) from exc
            raise
        return {"operator": operator.operator_id, **result}
