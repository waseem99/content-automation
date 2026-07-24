from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth
from src.operator_api.studio_v2_runtime import StudioV2Service


class StudioContentStatesRequest(BaseModel):
    content_ids: list[UUID] = Field(min_length=1, max_length=100)


def install_studio_v2_batch_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    """Install bounded aggregate reads used by Creator Studio list screens."""
    if getattr(app.state, "studio_v2_batch_routes_installed", False):
        return
    app.state.studio_v2_batch_routes_installed = True

    service = StudioV2Service(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def require_service() -> StudioV2Service:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    @app.post("/studio-v2/content-states")
    def content_states(
        request: StudioContentStatesRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        ordered_ids = list(dict.fromkeys(request.content_ids))

        with require_database().connection() as conn:
            rows = conn.execute(
                """SELECT pc.id,mp.brand_id
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id = ANY(%s::uuid[])""",
                (ordered_ids,),
            ).fetchall()

        brands_by_content = {UUID(str(row["id"])): str(row["brand_id"]) for row in rows}
        missing = [str(content_id) for content_id in ordered_ids if content_id not in brands_by_content]
        if missing:
            raise HTTPException(
                status_code=404,
                detail={"code": "content_not_found", "content_ids": missing},
            )

        for content_id in ordered_ids:
            require_access(
                operator,
                AccessPermission.READ_PORTFOLIO,
                brand_id=brands_by_content[content_id],
            )

        items = [require_service().content_state(content_id) for content_id in ordered_ids]
        return {
            "ok": True,
            "kind": "studio_v2_content_states",
            "operator": operator.operator_id,
            "count": len(items),
            "items": items,
        }


__all__ = [
    "StudioContentStatesRequest",
    "install_studio_v2_batch_routes",
]
