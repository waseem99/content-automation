from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.performance import (
    ExperimentCreateRequest,
    ExperimentEvaluateRequest,
    PerformanceAnalyticsError,
    PerformanceAnalyticsService,
    PerformanceImportRequest,
    RecommendationRequest,
)
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
    visible_brand_ids,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_performance_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "performance_routes_installed", False):
        return
    app.state.performance_routes_installed = True
    service = PerformanceAnalyticsService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> PerformanceAnalyticsService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def require_admin(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)

    def require_read(operator: OperatorIdentity, *, brand_id: UUID | None = None) -> None:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=str(brand_id) if brand_id is not None else None,
        )

    def require_reviewer(operator: OperatorIdentity, *, brand_id: UUID) -> None:
        require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=str(brand_id))

    def experiment_brand(experiment_id: UUID) -> UUID:
        with require_database().connection() as conn:
            row = conn.execute(
                "SELECT brand_id FROM football_brief.performance_experiments WHERE id=%s",
                (experiment_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="performance_experiment_not_found")
        return row["brand_id"]

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except PerformanceAnalyticsError as exc:
            status = 409
            if exc.code in {
                "performance_import_batch_not_found",
                "performance_experiment_not_found",
                "performance_delivery_not_found",
            }:
                status = 404
            elif exc.code == "operator_inactive_or_missing":
                status = 403
            elif exc.code in {
                "performance_delivery_not_succeeded",
                "performance_observation_brand_mismatch",
                "performance_observation_platform_mismatch",
            }:
                status = 422
            raise HTTPException(status_code=status, detail={"code": exc.code, **exc.details}) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "performance_analytics_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.post("/performance/imports")
    def import_performance(
        request: PerformanceImportRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().import_batch(request, actor=operator.operator_id)),
        }

    @app.get("/performance/imports/{batch_id}")
    def performance_import_detail(
        batch_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        result = invoke(lambda: require_service().import_detail(batch_id=batch_id))
        require_read(operator, brand_id=result["batch"]["brand_id"])
        return {"operator": operator.operator_id, **result}

    @app.get("/performance/observations")
    def list_performance_observations(
        observed_from: datetime | None = Query(default=None),
        observed_to: datetime | None = Query(default=None),
        latest_per_delivery: bool = Query(default=False),
        limit: int = Query(default=200, ge=1, le=1000),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_read(operator)
        visible = visible_brand_ids(operator)
        brand_ids = None if visible is None else [UUID(item) for item in visible]
        return {
            "ok": True,
            "operator": operator.operator_id,
            "items": invoke(
                lambda: require_service().list_observations(
                    brand_ids=brand_ids,
                    observed_from=observed_from,
                    observed_to=observed_to,
                    latest_per_delivery=latest_per_delivery,
                    limit=limit,
                )
            ),
        }

    @app.get("/performance/dashboard/{brand_id}")
    def performance_dashboard(
        brand_id: UUID,
        observed_from: datetime | None = Query(default=None),
        observed_to: datetime | None = Query(default=None),
        minimum_items: int = Query(default=3, ge=1, le=1000),
        minimum_normalized_views: int = Query(default=1000, ge=0),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_read(operator, brand_id=brand_id)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().dashboard(
                    brand_id=brand_id,
                    observed_from=observed_from,
                    observed_to=observed_to,
                    minimum_items=minimum_items,
                    minimum_normalized_views=minimum_normalized_views,
                )
            ),
        }

    @app.post("/performance/experiments")
    def create_performance_experiment(
        request: ExperimentCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().create_experiment(request, actor=operator.operator_id)),
        }

    @app.get("/performance/experiments")
    def list_performance_experiments(
        limit: int = Query(default=100, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_read(operator)
        visible = visible_brand_ids(operator)
        brand_ids = None if visible is None else [UUID(item) for item in visible]
        return {
            "ok": True,
            "operator": operator.operator_id,
            "items": invoke(
                lambda: require_service().list_experiments(brand_ids=brand_ids, limit=limit)
            ),
        }

    @app.get("/performance/experiments/{experiment_id}")
    def performance_experiment_detail(
        experiment_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = experiment_brand(experiment_id)
        require_read(operator, brand_id=brand_id)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().experiment_detail(experiment_id=experiment_id)),
        }

    @app.post("/performance/experiments/{experiment_id}/activate")
    def activate_performance_experiment(
        experiment_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().activate_experiment(
                    experiment_id=experiment_id,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/performance/experiments/{experiment_id}/evaluate")
    def evaluate_performance_experiment(
        experiment_id: UUID,
        request: ExperimentEvaluateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = experiment_brand(experiment_id)
        require_reviewer(operator, brand_id=brand_id)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().evaluate_experiment(
                    experiment_id=experiment_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/performance/recommendations")
    def create_performance_recommendation(
        request: RecommendationRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_reviewer(operator, brand_id=request.brand_id)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().create_recommendation(
                    request,
                    actor=operator.operator_id,
                )
            ),
        }
