from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord
from src.domain.workflow_status import ProviderCallStatus


class HumanReviewCreate(FrozenRecord):
    workflow_run_id: UUID
    review_type: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    stage_execution_id: UUID | None = None
    checklist: dict[str, Any] = Field(default_factory=dict)


class HumanReview(HumanReviewCreate):
    id: UUID
    created_at: datetime


class ProviderCallCreate(FrozenRecord):
    stage_execution_id: UUID
    provider: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ProviderCallStatus = ProviderCallStatus.PENDING
    provider_request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderCall(ProviderCallCreate):
    id: UUID
    response_fingerprint: str | None = None
    units: Decimal | None = None
    unit_name: str | None = None
    cost_usd: Decimal
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class CostEntryCreate(FrozenRecord):
    workflow_run_id: UUID
    category: str = Field(min_length=1)
    amount_usd: Decimal = Field(ge=0)
    stage_execution_id: UUID | None = None
    provider_call_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_name: str | None = None


class CostEntry(CostEntryCreate):
    id: UUID
    created_at: datetime
