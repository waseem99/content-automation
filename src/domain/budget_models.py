from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord


class ProviderCallStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BudgetDecision(StrEnum):
    ALLOW = "allow"
    STOP = "stop"
    NEEDS_APPROVAL = "needs_approval"


class BudgetStopReason(StrEnum):
    WORKFLOW_LIMIT = "WORKFLOW_LIMIT"
    STAGE_LIMIT = "STAGE_LIMIT"
    PROVIDER_LIMIT = "PROVIDER_LIMIT"
    DAILY_LIMIT = "DAILY_LIMIT"
    UNKNOWN_PRICING = "UNKNOWN_PRICING"
    PREMIUM_REQUIRES_APPROVAL = "PREMIUM_REQUIRES_APPROVAL"


class ProviderPricing(FrozenRecord):
    provider: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    model_id: str | None = None
    unit_name: str = Field(min_length=1)
    unit_cost_usd: Decimal = Field(ge=0)
    profile_version: str = Field(default="pricing-v1", min_length=1)
    premium: bool = False


class BudgetLimit(FrozenRecord):
    workflow_limit_usd: Decimal | None = Field(default=None, ge=0)
    stage_limit_usd: Decimal | None = Field(default=None, ge=0)
    provider_limit_usd: Decimal | None = Field(default=None, ge=0)
    daily_limit_usd: Decimal | None = Field(default=None, ge=0)
    premium_threshold_usd: Decimal | None = Field(default=None, ge=0)
    require_approval_for_premium: bool = True


class BudgetCheckRequest(FrozenRecord):
    workflow_run_id: UUID
    stage_execution_id: UUID | None = None
    provider: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    model_id: str | None = None
    units: Decimal = Field(ge=0)
    actor: str = Field(min_length=1)
    today: date | None = None


class BudgetCheckResult(FrozenRecord):
    decision: BudgetDecision
    estimated_cost_usd: Decimal
    reasons: tuple[BudgetStopReason, ...] = ()
    pricing_profile: str | None = None
    requires_review: bool = False


class ProviderCallCreate(FrozenRecord):
    stage_execution_id: UUID
    provider: str
    operation: str
    provider_request_id: str | None = None
    idempotency_key: str
    status: ProviderCallStatus
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    units: Decimal | None = Field(default=None, ge=0)
    unit_name: str | None = None
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    model_id: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    error_classification: str | None = None
    pricing_profile: str | None = None
    budget_policy_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderCall(ProviderCallCreate):
    id: UUID
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class CostEntryCreate(FrozenRecord):
    workflow_run_id: UUID
    stage_execution_id: UUID | None = None
    provider_call_id: UUID | None = None
    category: str = Field(min_length=1)
    amount_usd: Decimal = Field(ge=0)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_name: str | None = None
    pricing_profile: str | None = None
    reconciliation_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CostEntry(CostEntryCreate):
    id: UUID
    created_at: datetime


class CostReconciliationReport(FrozenRecord):
    workflow_run_id: UUID
    cost_entry_total_usd: Decimal
    provider_call_total_usd: Decimal
    workflow_actual_cost_usd: Decimal
    matched: bool
    provider_mismatch_usd: Decimal
