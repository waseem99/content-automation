from __future__ import annotations

from datetime import date
from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.routing.models import (
    BudgetPolicyRequest,
    ReserveAndEnqueueRequest,
    RoutingPlanRequest,
    SpendDecisionRequest,
    SubmitRoutingPlanRequest,
)
from src.application.routing.service import RoutingSpendError, RoutingSpendService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_routing_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "routing_routes_installed", False):
        return
    app.state.routing_routes_installed = True
    service = RoutingSpendService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> RoutingSpendService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def content_brand_id(content_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="content_not_found")
        return str(row["brand_id"])

    def plan_brand_id(plan_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.shot_routing_plans srp
                   JOIN football_brief.portfolio_content pc ON pc.id=srp.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE srp.id=%s""",
                (plan_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="routing_plan_not_found")
        return str(row["brand_id"])

    def invoke(call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return call()
        except RoutingSpendError as exc:
            raise_routing_error(exc)
        except psycopg.Error as exc:
            message = str(exc).splitlines()[0][:500]
            raise HTTPException(
                status_code=422,
                detail={"code": "routing_spend_integrity_violation", "message": message},
            ) from exc

    @app.get("/routing/policies")
    def list_budget_policies(
        brand_id: UUID | None = Query(default=None),
        month_start: date | None = Query(default=None),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id) if brand_id else None)
        if not operator.is_admin and brand_id is None:
            raise HTTPException(status_code=422, detail="brand_id_required")
        policies = require_service().list_policies(brand_id=brand_id, month_start=month_start)
        return {"ok": True, "operator": operator.operator_id, "policies": policies}

    @app.post("/routing/policies")
    def create_budget_policy(
        request: BudgetPolicyRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().create_policy(request=request, actor=operator.operator_id)),
        }

    @app.post("/routing/policies/{policy_id}/activate")
    def activate_budget_policy(
        policy_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().activate_policy(policy_id=policy_id, actor=operator.operator_id)),
        }

    @app.post("/routing/content/{content_id}/plans")
    def create_routing_plan(
        content_id: UUID,
        request: RoutingPlanRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=content_brand_id(content_id),
        )
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().create_plan(
                    content_id=content_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.get("/routing/plans/{plan_id}")
    def routing_plan_detail(
        plan_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=plan_brand_id(plan_id),
        )
        return {"operator": operator.operator_id, **invoke(lambda: require_service().detail(plan_id=plan_id))}

    @app.post("/routing/plans/{plan_id}/submit")
    def submit_routing_plan(
        plan_id: UUID,
        request: SubmitRoutingPlanRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=plan_brand_id(plan_id),
        )
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().submit(
                    plan_id=plan_id,
                    expected_lock_version=request.expected_lock_version,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/routing/plans/{plan_id}/decisions")
    def decide_routing_plan(
        plan_id: UUID,
        request: SpendDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=plan_brand_id(plan_id),
        )
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().decide(
                    plan_id=plan_id,
                    request=request,
                    reviewer=operator.operator_id,
                )
            ),
        }

    @app.post("/routing/plans/{plan_id}/managed-jobs")
    def reserve_and_enqueue_managed_job(
        plan_id: UUID,
        request: ReserveAndEnqueueRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=plan_brand_id(plan_id),
        )
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().reserve_and_enqueue(
                    plan_id=plan_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }


def raise_routing_error(exc: RoutingSpendError) -> None:
    if exc.code in {
        "content_not_found",
        "budget_policy_not_found",
        "budget_policy_parent_not_found",
        "routing_plan_not_found",
        "routing_parent_not_found",
        "managed_routing_item_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "budget_policy_parent_required",
        "budget_policy_not_draft",
        "routing_plan_conflict_or_not_draft",
        "spend_reservation_not_available",
        "spend_reservation_binding_conflict",
        "content_version_conflict",
    }:
        status_code = 409
    elif exc.code == "operator_inactive_or_missing":
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, **exc.details},
    ) from exc
