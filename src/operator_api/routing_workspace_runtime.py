from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException

from src.application.routing.service import RoutingSpendError, RoutingSpendService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_routing_workspace_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "routing_workspace_routes_installed", False):
        return
    app.state.routing_workspace_routes_installed = True
    service = RoutingSpendService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    @app.get("/routing/content/{content_id}/current")
    def current_content_routing(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if database is None or service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                """SELECT srp.id,mp.brand_id
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   LEFT JOIN football_brief.shot_routing_plans srp
                     ON srp.portfolio_content_id=pc.id AND srp.content_version=pc.version
                   WHERE pc.id=%s
                   ORDER BY srp.version DESC NULLS LAST,srp.created_at DESC NULLS LAST
                   LIMIT 1""",
                (content_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="content_not_found")
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=str(row["brand_id"]),
        )
        if row["id"] is None:
            raise HTTPException(status_code=404, detail="routing_plan_not_found")
        try:
            return {"operator": operator.operator_id, **service.detail(plan_id=row["id"])}
        except RoutingSpendError as exc:
            raise HTTPException(
                status_code=404 if exc.code == "routing_plan_not_found" else 422,
                detail={"code": exc.code, **exc.details},
            ) from exc
