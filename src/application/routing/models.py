from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ShotRoute(StrEnum):
    DETERMINISTIC_ANIMATION = "deterministic_animation"
    LOCAL_RENDER = "local_render"
    MANAGED_RENDER = "managed_render"
    MANUAL_EDIT = "manual_edit"


class SpendDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class BudgetPolicyRequest(BaseModel):
    brand_id: UUID
    month_start: date
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    monthly_soft_limit: Decimal = Field(ge=0)
    monthly_hard_limit: Decimal = Field(ge=0)
    default_content_limit: Decimal = Field(ge=0)
    approval_threshold: Decimal = Field(default=Decimal("0"), ge=0)
    require_approval_for_managed: bool = True
    parent_policy_id: UUID | None = None

    @model_validator(mode="after")
    def validate_limits(self) -> "BudgetPolicyRequest":
        if self.month_start.day != 1:
            raise ValueError("month_start must be the first day of the month")
        if self.monthly_soft_limit > self.monthly_hard_limit:
            raise ValueError("monthly_soft_limit cannot exceed monthly_hard_limit")
        if self.default_content_limit > self.monthly_hard_limit:
            raise ValueError("default_content_limit cannot exceed monthly_hard_limit")
        if self.approval_threshold > self.monthly_hard_limit:
            raise ValueError("approval_threshold cannot exceed monthly_hard_limit")
        return self


class ShotRoutingInput(BaseModel):
    visual_shot_id: UUID
    renderer_preflight_id: UUID | None = None
    hero_importance: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    realism_requirement: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    motion_complexity: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    continuity_requirement: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    factual_control_requirement: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    local_preview_quality: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    engagement_contribution: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    forced_route: ShotRoute | None = None
    override_rationale: str | None = Field(default=None, min_length=3, max_length=5000)

    @model_validator(mode="after")
    def validate_override(self) -> "ShotRoutingInput":
        if self.forced_route is not None and not self.override_rationale:
            raise ValueError("forced_route requires override_rationale")
        if self.forced_route == ShotRoute.MANAGED_RENDER and self.renderer_preflight_id is None:
            raise ValueError("managed route requires renderer_preflight_id")
        return self


class RoutingPlanRequest(BaseModel):
    budget_policy_id: UUID
    shots: tuple[ShotRoutingInput, ...] = Field(min_length=1, max_length=200)
    recommendation_context: dict[str, Any] = Field(default_factory=dict)
    parent_plan_id: UUID | None = None

    @model_validator(mode="after")
    def unique_shots(self) -> "RoutingPlanRequest":
        shot_ids = [item.visual_shot_id for item in self.shots]
        if len(set(shot_ids)) != len(shot_ids):
            raise ValueError("each visual shot may appear only once")
        return self


class SubmitRoutingPlanRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)


class SpendDecisionRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)
    decision: SpendDecision
    approved_ceiling: Decimal | None = Field(default=None, ge=0)
    rationale: str = Field(min_length=3, max_length=5000)

    @model_validator(mode="after")
    def approval_ceiling(self) -> "SpendDecisionRequest":
        if self.decision == SpendDecision.APPROVED and self.approved_ceiling is None:
            raise ValueError("approved decision requires approved_ceiling")
        return self


class ReserveAndEnqueueRequest(BaseModel):
    routing_item_id: UUID
    production_workflow_id: UUID | None = None
    production_workflow_version_id: UUID | None = None
    preferred_worker_id: str | None = Field(default=None, max_length=200)
    priority: int = Field(default=0, ge=-1000, le=1000)
    timeout_seconds: int = Field(default=1800, ge=5, le=86400)
    max_attempts: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def workflow_pair(self) -> "ReserveAndEnqueueRequest":
        if self.production_workflow_version_id is not None and self.production_workflow_id is None:
            raise ValueError("production_workflow_id is required with production_workflow_version_id")
        return self
