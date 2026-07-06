from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from src.domain.base import FrozenRecord


class WorkerFailureClass(StrEnum):
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    TIMEOUT = "timeout"


class WorkerOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REUSED = "reused"
    ALREADY_RUNNING = "already_running"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class WorkerRetryPolicy(FrozenRecord):
    max_attempts: int = Field(default=3, ge=1)
    retryable_failures: tuple[WorkerFailureClass, ...] = (
        WorkerFailureClass.RETRYABLE,
        WorkerFailureClass.TIMEOUT,
        WorkerFailureClass.SCHEMA_VALIDATION_FAILED,
    )


class WorkerDefinition(FrozenRecord):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    input_schema_name: str = Field(min_length=1)
    input_schema_version: str = Field(min_length=1)
    output_schema_name: str = Field(min_length=1)
    output_schema_version: str = Field(min_length=1)
    timeout_seconds: int = Field(default=60, gt=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    requires_human_approval: bool = False
    reuse_successful_outputs: bool = True
    invalidates_downstream: bool = True
    retry_policy: WorkerRetryPolicy = Field(default_factory=WorkerRetryPolicy)
    idempotency_fields: tuple[str, ...] = ()


class WorkerExecutionRequest(FrozenRecord):
    workflow_run_id: UUID
    worker_name: str = Field(min_length=1)
    worker_version: str = Field(min_length=1)
    input_payload: dict[str, Any]
    actor: str = Field(min_length=1)
    stage_name: str | None = None
    provider: str | None = None
    operation: str | None = None
    provider_request_id: str | None = None
    provider_model_id: str | None = None
    provider_units: Decimal = Field(default=Decimal("1"), ge=0)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)


class WorkerOutputEnvelope(FrozenRecord):
    output: dict[str, Any]
    output_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_request_id: str | None = None
    units: Decimal | None = Field(default=None, ge=0)
    unit_name: str | None = None
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerExecutionResult(FrozenRecord):
    outcome: WorkerOutcome
    stage_execution_id: UUID | None = None
    idempotency_key: str
    input_hash: str
    output_hash: str | None = None
    output: dict[str, Any] | None = None
    attempt: int | None = None
    reused: bool = False
    failure_class: WorkerFailureClass | None = None
    failure_reason: str | None = None


class WorkerFailure(Exception):
    def __init__(self, failure_class: WorkerFailureClass, message: str) -> None:
        super().__init__(message)
        self.failure_class = failure_class
        self.message = message


class WorkerHandlerResult(FrozenRecord):
    output: dict[str, Any]
    provider_request_id: str | None = None
    units: Decimal | None = Field(default=None, ge=0)
    unit_name: str | None = None
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_structured_output(self) -> "WorkerHandlerResult":
        if not self.output:
            raise ValueError("Worker output cannot be empty")
        return self


WorkerHandler = Callable[[dict[str, Any]], WorkerHandlerResult]
