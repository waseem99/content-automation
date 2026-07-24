from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder

from src.application.acceptance.controlled_snapshot_models import (
    PilotEvidenceSnapshotRequest,
)
from src.application.acceptance.controlled_snapshot_service import (
    ControlledEvidenceSnapshotService,
)
from src.application.acceptance.service import AcceptancePilotError
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_acceptance_controlled_snapshot_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "acceptance_controlled_snapshot_routes_installed", False):
        return
    app.state.acceptance_controlled_snapshot_routes_installed = True
    service = ControlledEvidenceSnapshotService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ControlledEvidenceSnapshotService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_snapshot_role(operator: OperatorIdentity, pilot_id: UUID) -> None:
        if not operator.is_admin and OperatorRole.REVIEWER not in operator.roles:
            raise HTTPException(status_code=403, detail="acceptance_snapshot_role_required")
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
            elif exc.code == "pilot_snapshot_duplicate_binding":
                status = 409
            raise HTTPException(
                status_code=status,
                detail=jsonable_encoder({"code": exc.code, **exc.details}),
            ) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "acceptance_snapshot_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.get("/acceptance/pilots/{pilot_id}/evidence-preview")
    def preview_evidence(
        pilot_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        invoke(lambda: require_snapshot_role(operator, pilot_id))
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().preview(pilot_id=pilot_id)),
        }

    @app.post("/acceptance/pilots/{pilot_id}/snapshot-evidence")
    def snapshot_evidence(
        pilot_id: UUID,
        request: PilotEvidenceSnapshotRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        invoke(lambda: require_snapshot_role(operator, pilot_id))
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().snapshot(
                    pilot_id=pilot_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }


__all__ = ["install_acceptance_controlled_snapshot_routes"]
