from __future__ import annotations

from typing import Any, Callable

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.acceptance.candidate_service import (
    AcceptanceCandidateError,
    AcceptanceCandidateService,
    REQUIRED_BRAND_SLUGS,
)
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_acceptance_candidate_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "acceptance_candidate_routes_installed", False):
        return
    app.state.acceptance_candidate_routes_installed = True
    service = AcceptanceCandidateService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> AcceptanceCandidateService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def required_brand_ids() -> set[str]:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            rows = conn.execute(
                """SELECT id,slug FROM football_brief.brands
                   WHERE slug=ANY(%s::text[]) ORDER BY slug""",
                (list(REQUIRED_BRAND_SLUGS),),
            ).fetchall()
        found = {row["slug"] for row in rows}
        missing = sorted(set(REQUIRED_BRAND_SLUGS) - found)
        if missing:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "required_pilot_brands_missing",
                    "missing_brand_slugs": missing,
                },
            )
        return {str(row["id"]) for row in rows}

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except AcceptanceCandidateError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.code, **exc.details},
            ) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "acceptance_candidate_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.get("/acceptance/pilot-candidates")
    def pilot_candidates(
        limit_per_brand: int = Query(default=50, ge=1, le=100),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin and not operator.roles.intersection(
            {OperatorRole.REVIEWER, OperatorRole.PUBLISHER}
        ):
            raise HTTPException(status_code=403, detail="acceptance_read_role_required")
        required_brands = required_brand_ids()
        if not operator.is_admin and not required_brands.issubset(set(operator.brand_ids)):
            raise HTTPException(status_code=403, detail="pilot_brand_scope_required")
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().inventory(limit_per_brand=limit_per_brand)),
        }


__all__ = ["install_acceptance_candidate_routes"]
