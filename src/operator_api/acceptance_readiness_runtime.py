from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException

from src.application.acceptance import AcceptancePilotError, AcceptancePilotService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_acceptance_readiness_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "acceptance_readiness_routes_installed", False):
        return
    app.state.acceptance_readiness_routes_installed = True
    service = AcceptancePilotService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> AcceptancePilotService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def required_brand_ids(pilot_id: UUID) -> set[str]:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            rows = conn.execute(
                """SELECT b.id
                   FROM football_brief.acceptance_pilots ap
                   JOIN LATERAL jsonb_array_elements_text(ap.scope->'brand_slugs') slug(value)
                     ON true
                   JOIN football_brief.brands b ON b.slug=slug.value
                   WHERE ap.id=%s""",
                (pilot_id,),
            ).fetchall()
            exists = conn.execute(
                "SELECT EXISTS(SELECT 1 FROM football_brief.acceptance_pilots WHERE id=%s) AS found",
                (pilot_id,),
            ).fetchone()["found"]
        if not exists:
            raise HTTPException(
                status_code=404,
                detail={"code": "pilot_not_found"},
            )
        return {str(row["id"]) for row in rows}

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except AcceptancePilotError as exc:
            status = 404 if exc.code == "pilot_not_found" else 422
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code, **exc.details},
            ) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "acceptance_readiness_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.get("/acceptance/pilots/{pilot_id}/readiness")
    def pilot_readiness(
        pilot_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin and not operator.roles.intersection(
            {OperatorRole.REVIEWER, OperatorRole.PUBLISHER}
        ):
            raise HTTPException(status_code=403, detail="acceptance_read_role_required")
        required_brands = required_brand_ids(pilot_id)
        if not operator.is_admin and not required_brands.issubset(set(operator.brand_ids)):
            raise HTTPException(status_code=403, detail="pilot_brand_scope_required")
        report = invoke(lambda: require_service().readiness(pilot_id=pilot_id))
        return {"operator": operator.operator_id, **report}


__all__ = ["install_acceptance_readiness_routes"]
