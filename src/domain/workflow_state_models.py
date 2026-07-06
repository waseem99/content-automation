from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.domain.base import FrozenRecord
from src.domain.workflow_status import StageStatus, WorkflowStatus


class TransitionReasonCode(StrEnum):
    INVALID_TRANSITION = "INVALID_TRANSITION"
    IDENTITY_REQUIRED = "IDENTITY_REQUIRED"
    REQUIRED_STAGE_NOT_COMPLETE = "REQUIRED_STAGE_NOT_COMPLETE"
    WORKFLOW_NOT_ACTIVE = "WORKFLOW_NOT_ACTIVE"
    STAGE_NOT_RETRYABLE = "STAGE_NOT_RETRYABLE"
    STALE_OUTPUT = "STALE_OUTPUT"


class TransitionActorType(StrEnum):
    SYSTEM = "system"
    WORKER = "worker"
    OPERATOR = "operator"


class WorkflowTransitionRequest(FrozenRecord):
    workflow_run_id: UUID
    target_status: WorkflowStatus
    actor: str = Field(min_length=1)
    actor_type: TransitionActorType = TransitionActorType.SYSTEM
    reason: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class StageTransitionRequest(FrozenRecord):
    stage_execution_id: UUID
    target_status: StageStatus
    actor: str = Field(min_length=1)
    actor_type: TransitionActorType = TransitionActorType.SYSTEM
    reason: str = Field(min_length=1)
    output_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    failure_reason: str | None = None
    output: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class StageDependencyCreate(FrozenRecord):
    workflow_run_id: UUID
    upstream_stage_execution_id: UUID
    downstream_stage_execution_id: UUID
    expected_upstream_output_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResumePlan(FrozenRecord):
    workflow_run_id: UUID
    runnable_stage_ids: tuple[UUID, ...]
    skipped_stage_ids: tuple[UUID, ...]
    blocked_stage_ids: tuple[UUID, ...]
