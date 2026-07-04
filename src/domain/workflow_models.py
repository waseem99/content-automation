from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord
from src.domain.workflow_status import StageStatus, WorkflowStatus


class WorkflowRunCreate(FrozenRecord):
    content_item_id: UUID
    workflow_name: str = Field(min_length=1)
    workflow_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_budget_usd: Decimal | None = Field(default=None, ge=0)
    current_stage: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRun(WorkflowRunCreate):
    id: UUID
    status: WorkflowStatus
    actual_cost_usd: Decimal
    started_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StageExecutionCreate(FrozenRecord):
    workflow_run_id: UUID
    stage_name: str = Field(min_length=1)
    stage_version: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt: int = Field(default=1, ge=1)
    status: StageStatus = StageStatus.PENDING
    model_or_tool: str | None = None
    prompt_version: str | None = None
    timeout_seconds: int | None = Field(default=None, gt=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    operator: str | None = None


class StageExecution(StageExecutionCreate):
    id: UUID
    output_hash: str | None = None
    actual_cost_usd: Decimal
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int
    warnings: list[Any]
    output: dict[str, Any] | None = None
    failure_reason: str | None = None
    created_at: datetime
