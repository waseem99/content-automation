from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class GenerationJobType(StrEnum):
    CONCEPT = "concept"
    SCRIPT = "script"
    NARRATION = "narration"
    KEYFRAME = "keyframe"
    PREVIEW = "preview"
    LOCAL_CLIP = "local_clip"
    PREMIUM_CLIP = "premium_clip"
    ASSEMBLY = "assembly"
    CAPTION = "caption"
    THUMBNAIL = "thumbnail"
    PACKAGE = "package"
    PUBLISHING = "publishing"


class GenerationJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class GenerationAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ABANDONED = "abandoned"


class GenerationJobEnqueue(BaseModel):
    portfolio_content_id: UUID
    content_version: int = Field(ge=1)
    production_workflow_id: UUID | None = None
    production_workflow_version_id: UUID | None = None
    job_type: GenerationJobType
    provider: str | None = Field(default=None, max_length=120)
    model_id: str | None = Field(default=None, max_length=200)
    preferred_worker_id: str | None = Field(default=None, max_length=200)
    priority: int = Field(default=0, ge=-1000, le=1000)
    idempotency_key: str = Field(min_length=8, max_length=240)
    input_payload: dict[str, Any]
    timeout_seconds: int = Field(default=300, ge=5, le=86400)
    max_attempts: int = Field(default=3, ge=1, le=10)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    reserved_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    dependency_job_ids: tuple[UUID, ...] = ()
    legacy_source: dict[str, Any] = Field(default_factory=dict)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be blank")
        return normalized

    @field_validator("provider", "model_id", "preferred_worker_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_workflow_pair_and_dependencies(self) -> "GenerationJobEnqueue":
        if self.production_workflow_version_id is not None and self.production_workflow_id is None:
            raise ValueError("production_workflow_id is required with production_workflow_version_id")
        if len(set(self.dependency_job_ids)) != len(self.dependency_job_ids):
            raise ValueError("dependency_job_ids must be unique")
        return self


class GenerationJobClaimRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=200)
    lease_seconds: int = Field(default=120, ge=15, le=3600)
    job_types: tuple[GenerationJobType, ...] = ()
    providers: tuple[str, ...] = ()


class GenerationJobHeartbeat(BaseModel):
    job_id: UUID
    attempt_id: UUID
    lease_token: UUID
    worker_id: str = Field(min_length=1, max_length=200)
    lease_seconds: int = Field(default=120, ge=15, le=3600)


class GenerationJobCompletion(BaseModel):
    job_id: UUID
    attempt_id: UUID
    lease_token: UUID
    worker_id: str = Field(min_length=1, max_length=200)
    output_payload: dict[str, Any]
    actual_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    provider_request_id: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def require_output(self) -> "GenerationJobCompletion":
        if not self.output_payload:
            raise ValueError("output_payload cannot be empty")
        return self


class GenerationJobFailure(BaseModel):
    job_id: UUID
    attempt_id: UUID
    lease_token: UUID
    worker_id: str = Field(min_length=1, max_length=200)
    error_code: str = Field(min_length=1, max_length=120)
    error_message: str = Field(min_length=1, max_length=5000)
    retryable: bool
    actual_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    error_details: dict[str, Any] = Field(default_factory=dict)


class LegacyGenerationRecord(BaseModel):
    legacy_id: str = Field(min_length=1, max_length=240)
    status: str = Field(min_length=1, max_length=40)
    job_type: GenerationJobType = GenerationJobType.KEYFRAME
    provider: str | None = None
    model_id: str | None = None
    worker_id: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    actual_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    attempt_count: int = Field(default=1, ge=0, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)
