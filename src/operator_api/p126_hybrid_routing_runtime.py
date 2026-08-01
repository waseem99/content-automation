from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.application.hybrid_routing import HybridRoutingError, HybridRoutingService, ROUTE_CLASSES
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class PlanPackageRequest(BaseModel):
    deadline_at: datetime | None = None


class HybridPolicyRequest(BaseModel):
    maximum_content_cost: Decimal = Field(default=Decimal("0"), ge=0)
    maximum_scene_cost: Decimal = Field(default=Decimal("0"), ge=0)
    default_quality_floor: float = Field(default=75, ge=0, le=100)
    hero_quality_floor: float = Field(default=86, ge=0, le=100)
    maximum_attempts: int = Field(default=3, ge=1, le=10)
    scoring_weights: dict[str, float] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)


class TemplateRequest(BaseModel):
    template_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    category: Literal[
        "intro",
        "outro",
        "caption",
        "background",
        "transition",
        "map",
        "diagram",
        "brand_treatment",
        "reusable_asset",
    ]
    specification: dict[str, Any]
    asset_id: UUID | None = None
    duration_seconds: float | None = Field(default=None, gt=0)
    quality_rating: float = Field(default=85, ge=0, le=100)
    supported_formats: list[str] = Field(default_factory=list, max_length=50)
    supported_territories: list[str] = Field(default_factory=lambda: ["global"], max_length=100)
    activate: bool = True


class MeasurementRequest(BaseModel):
    measurement_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    route_class: Literal[
        "reuse_asset",
        "deterministic_composition",
        "local_generation",
        "cloud_portable",
        "premium_low_cost",
        "premium_hero",
        "manual_edit",
    ]
    renderer_catalogue_entry_id: UUID | None = None
    local_video_workflow_id: UUID | None = None
    template_id: UUID | None = None
    acceptance_rate: float = Field(ge=0, le=1)
    cost_per_accepted_second: Decimal = Field(default=Decimal("0"), ge=0)
    queue_eta_p50_seconds: int = Field(default=0, ge=0)
    queue_eta_p95_seconds: int = Field(default=0, ge=0)
    quality_score: float = Field(ge=0, le=100)
    continuity_risk: float = Field(default=0, ge=0, le=100)
    hardware_available: bool = True
    sample_size: int = Field(default=0, ge=0)
    supported_territories: list[str] = Field(default_factory=lambda: ["global"], max_length=100)
    evidence: dict[str, Any]
    observed_at: datetime
    activate: bool = True


class OverrideSceneRequest(BaseModel):
    candidate_id: UUID
    rationale: str = Field(min_length=5, max_length=5000)


class SpendDecisionRequest(BaseModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    approved_ceiling: Decimal | None = Field(default=None, ge=0)
    rationale: str = Field(min_length=3, max_length=5000)


class CreateAttemptRequest(BaseModel):
    candidate_id: UUID
    billing_key: str = Field(min_length=8, max_length=240)


class CompleteAttemptRequest(BaseModel):
    status: Literal["accepted", "failed", "rejected", "cancelled"]
    rendered_seconds: float = Field(ge=0)
    accepted_seconds: float = Field(default=0, ge=0)
    actual_cost: Decimal = Field(default=Decimal("0"), ge=0)
    failure_code: str | None = Field(default=None, max_length=160)
    evidence: dict[str, Any] = Field(default_factory=dict)


def install_p126_hybrid_routing_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "p126_hybrid_routing_routes_installed", False):
        return
    app.state.p126_hybrid_routing_routes_installed = True
    service = HybridRoutingService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> HybridRoutingService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_admin(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")

    def brand_for_package(package_id: UUID) -> str:
        return _brand_id(
            database,
            """SELECT campaign.brand_id
               FROM football_brief.pre_generation_packages package_row
               JOIN football_brief.production_campaign_items item ON item.id=package_row.campaign_item_id
               JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
               JOIN football_brief.production_campaigns campaign ON campaign.id=version.campaign_id
               WHERE package_row.id=%s""",
            package_id,
            "pre_generation_package_not_found",
        )

    def brand_for_plan(plan_id: UUID) -> str:
        return _brand_id(
            database,
            """SELECT campaign.brand_id
               FROM football_brief.hybrid_route_plans route_plan
               JOIN football_brief.production_campaign_items item ON item.id=route_plan.campaign_item_id
               JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
               JOIN football_brief.production_campaigns campaign ON campaign.id=version.campaign_id
               WHERE route_plan.id=%s""",
            plan_id,
            "hybrid_route_plan_not_found",
        )

    def brand_for_scene(scene_id: UUID) -> str:
        return _brand_id(
            database,
            """SELECT campaign.brand_id
               FROM football_brief.hybrid_route_scenes scene
               JOIN football_brief.hybrid_route_plans route_plan ON route_plan.id=scene.route_plan_id
               JOIN football_brief.production_campaign_items item ON item.id=route_plan.campaign_item_id
               JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
               JOIN football_brief.production_campaigns campaign ON campaign.id=version.campaign_id
               WHERE scene.id=%s""",
            scene_id,
            "hybrid_route_scene_not_found",
        )

    def brand_for_attempt(attempt_id: UUID) -> str:
        return _brand_id(
            database,
            """SELECT campaign.brand_id
               FROM football_brief.hybrid_route_attempts attempt
               JOIN football_brief.hybrid_route_scenes scene ON scene.id=attempt.route_scene_id
               JOIN football_brief.hybrid_route_plans route_plan ON route_plan.id=scene.route_plan_id
               JOIN football_brief.production_campaign_items item ON item.id=route_plan.campaign_item_id
               JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
               JOIN football_brief.production_campaigns campaign ON campaign.id=version.campaign_id
               WHERE attempt.id=%s""",
            attempt_id,
            "hybrid_route_attempt_not_found",
        )

    @app.post("/p126/brands/{brand_id}/policy")
    def configure_policy(
        brand_id: UUID,
        request: HybridPolicyRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        require_access(operator, AccessPermission.MANAGE_BRANDS, brand_id=str(brand_id))
        try:
            return {
                "operator": operator.operator_id,
                **require_service().configure_policy(
                    brand_id=brand_id,
                    actor=operator.operator_id,
                    maximum_content_cost=request.maximum_content_cost,
                    maximum_scene_cost=request.maximum_scene_cost,
                    default_quality_floor=request.default_quality_floor,
                    hero_quality_floor=request.hero_quality_floor,
                    maximum_attempts=request.maximum_attempts,
                    scoring_weights=request.scoring_weights,
                    configuration=request.configuration,
                ),
            }
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.post("/p126/brands/{brand_id}/templates")
    def register_template(
        brand_id: UUID,
        request: TemplateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        require_access(operator, AccessPermission.MANAGE_BRANDS, brand_id=str(brand_id))
        try:
            return {
                "operator": operator.operator_id,
                **require_service().register_template(
                    template_key=request.template_key,
                    category=request.category,
                    specification=request.specification,
                    actor=operator.operator_id,
                    brand_id=brand_id,
                    asset_id=request.asset_id,
                    duration_seconds=request.duration_seconds,
                    quality_rating=request.quality_rating,
                    supported_formats=request.supported_formats,
                    supported_territories=request.supported_territories,
                    activate=request.activate,
                ),
            }
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.post("/p126/measurements")
    def record_measurement(
        request: MeasurementRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        require_access(operator, AccessPermission.MANAGE_BRANDS)
        if request.route_class not in ROUTE_CLASSES:
            raise HTTPException(status_code=422, detail="invalid_route_class")
        try:
            return {
                "operator": operator.operator_id,
                **require_service().record_measurement(
                    measurement_key=request.measurement_key,
                    route_class=request.route_class,
                    actor=operator.operator_id,
                    acceptance_rate=request.acceptance_rate,
                    quality_score=request.quality_score,
                    evidence=request.evidence,
                    observed_at=request.observed_at,
                    cost_per_accepted_second=request.cost_per_accepted_second,
                    queue_eta_p50_seconds=request.queue_eta_p50_seconds,
                    queue_eta_p95_seconds=request.queue_eta_p95_seconds,
                    continuity_risk=request.continuity_risk,
                    hardware_available=request.hardware_available,
                    sample_size=request.sample_size,
                    supported_territories=request.supported_territories,
                    renderer_catalogue_entry_id=request.renderer_catalogue_entry_id,
                    local_video_workflow_id=request.local_video_workflow_id,
                    template_id=request.template_id,
                    activate=request.activate,
                ),
            }
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.post("/p126/packages/{package_id}/plan")
    def plan_package(
        package_id: UUID,
        request: PlanPackageRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = brand_for_package(package_id)
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        try:
            return {
                "operator": operator.operator_id,
                **require_service().plan_package(
                    package_id=package_id,
                    actor=operator.operator_id,
                    deadline_at=request.deadline_at,
                ),
            }
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.get("/p126/plans/{plan_id}")
    def plan_detail(
        plan_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = brand_for_plan(plan_id)
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=brand_id)
        try:
            return {"operator": operator.operator_id, **require_service().detail(plan_id=plan_id)}
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.get("/p126/plans/{plan_id}/report")
    def plan_report(
        plan_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = brand_for_plan(plan_id)
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=brand_id)
        try:
            return {"operator": operator.operator_id, **require_service().report(plan_id=plan_id)}
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.post("/p126/scenes/{scene_id}/override")
    def override_scene(
        scene_id: UUID,
        request: OverrideSceneRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = brand_for_scene(scene_id)
        require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        try:
            return {
                "operator": operator.operator_id,
                **require_service().override_scene(
                    scene_id=scene_id,
                    candidate_id=request.candidate_id,
                    rationale=request.rationale,
                    actor=operator.operator_id,
                ),
            }
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.post("/p126/plans/{plan_id}/spend-decision")
    def spend_decision(
        plan_id: UUID,
        request: SpendDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        brand_id = brand_for_plan(plan_id)
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        try:
            return {
                "operator": operator.operator_id,
                **require_service().record_spend_decision(
                    plan_id=plan_id,
                    decision=request.decision,
                    approved_ceiling=request.approved_ceiling,
                    rationale=request.rationale,
                    actor=operator.operator_id,
                ),
            }
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.post("/p126/scenes/{scene_id}/attempts")
    def create_attempt(
        scene_id: UUID,
        request: CreateAttemptRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = brand_for_scene(scene_id)
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        try:
            return {
                "operator": operator.operator_id,
                **require_service().create_attempt(
                    scene_id=scene_id,
                    candidate_id=request.candidate_id,
                    billing_key=request.billing_key,
                    actor=operator.operator_id,
                ),
            }
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)

    @app.post("/p126/attempts/{attempt_id}/complete")
    def complete_attempt(
        attempt_id: UUID,
        request: CompleteAttemptRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = brand_for_attempt(attempt_id)
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        try:
            return {
                "operator": operator.operator_id,
                **require_service().complete_attempt(
                    attempt_id=attempt_id,
                    status=request.status,
                    rendered_seconds=request.rendered_seconds,
                    accepted_seconds=request.accepted_seconds,
                    actual_cost=request.actual_cost,
                    actor=operator.operator_id,
                    failure_code=request.failure_code,
                    evidence=request.evidence,
                ),
            }
        except HybridRoutingError as exc:
            raise_hybrid_error(exc)


def _brand_id(database: Database | None, query: str, value: UUID, missing_code: str) -> str:
    if database is None:
        raise HTTPException(status_code=503, detail="database_not_configured")
    with database.connection() as conn:
        row = conn.execute(query, (value,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=missing_code)
    return str(row["brand_id"])


def raise_hybrid_error(exc: HybridRoutingError) -> None:
    if exc.code.endswith("_not_found") or exc.code in {
        "pre_generation_package_not_found",
        "brand_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "operator_inactive_or_missing",
        "admin_required",
        "explicit_spend_approval_required",
    }:
        status_code = 403
    elif exc.code in {
        "billing_key_identity_mismatch",
        "candidate_must_be_selected_before_attempt",
        "hybrid_route_scene_not_attemptable",
        "hybrid_route_scene_not_overridable",
        "maximum_scene_attempts_reached",
        "local_route_not_exhausted",
        "spend_decision_already_recorded",
    }:
        status_code = 409
    else:
        status_code = 422
    raise HTTPException(status_code=status_code, detail={"code": exc.code, **exc.details}) from exc


__all__ = ["install_p126_hybrid_routing_routes"]
