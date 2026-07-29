from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class PilotRunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class PilotShotClass(StrEnum):
    EASY_MOTION = "easy_motion"
    PEOPLE_ANIMALS = "people_animals"
    PRODUCT = "product"
    MAP_DIAGRAM = "map_diagram"
    TRANSITION = "transition"
    HERO = "hero"


class PilotDifficulty(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DistributionScope(StrEnum):
    INTERNAL = "internal"
    TERRITORY_LIMITED = "territory_limited"
    GLOBAL_PUBLIC = "global_public"


class PilotAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PilotReviewDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class PilotRunCreateRequest(BaseModel):
    run_key: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    title: str = Field(min_length=3, max_length=300)
    target_videos: int = Field(default=3, ge=1, le=20)
    target_attempts: int = Field(default=30, ge=1, le=1000)
    hardware_snapshot: dict[str, Any] = Field(default_factory=dict)
    software_snapshot: dict[str, Any] = Field(default_factory=dict)
    baseline_assumptions: dict[str, Any] = Field(default_factory=dict)


class PilotRunStartRequest(BaseModel):
    hardware_snapshot: dict[str, Any] | None = None
    software_snapshot: dict[str, Any] | None = None


class PilotCaseCreateRequest(BaseModel):
    case_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    title: str = Field(min_length=3, max_length=300)
    shot_class: PilotShotClass
    difficulty: PilotDifficulty
    distribution_scope: DistributionScope
    release_territories: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    target_duration_seconds: Decimal = Field(ge=Decimal("1"), le=Decimal("15"))
    prompt: str = Field(min_length=3, max_length=10000)
    negative_prompt: str | None = Field(default=None, max_length=5000)
    input_asset_id: UUID | None = None
    required_model_keys: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    acceptance_criteria: dict[str, Any] = Field(default_factory=dict)

    @field_validator("release_territories", "required_model_keys")
    @classmethod
    def normalize_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))

    @model_validator(mode="after")
    def validate_territory_scope(self) -> "PilotCaseCreateRequest":
        if self.distribution_scope == DistributionScope.TERRITORY_LIMITED and not self.release_territories:
            raise ValueError("release_territories are required for territory_limited cases")
        return self


class ModelUsePreflightRequest(BaseModel):
    provider_key: str = Field(min_length=2, max_length=100)
    model_key: str = Field(min_length=1, max_length=200)
    distribution_scope: DistributionScope
    release_territories: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    written_clearance_reference: str | None = Field(default=None, min_length=3, max_length=2000)

    @field_validator("provider_key")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("release_territories")
    @classmethod
    def normalize_territories(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


class PilotAttemptCreateRequest(BaseModel):
    provider_key: str = Field(min_length=2, max_length=100)
    model_key: str = Field(min_length=1, max_length=200)
    renderer_catalogue_entry_id: UUID | None = None
    generation_job_id: UUID | None = None
    workflow_key: str = Field(min_length=2, max_length=200)
    workflow_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: int
    width: int = Field(ge=256, le=8192)
    height: int = Field(ge=256, le=8192)
    fps: int = Field(ge=1, le=240)
    frame_count: int = Field(ge=1, le=10000)
    inference_steps: int = Field(ge=1, le=500)
    started_at: datetime
    written_clearance_reference: str | None = Field(default=None, min_length=3, max_length=2000)

    @field_validator("provider_key")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()


class PilotAttemptCompleteRequest(BaseModel):
    status: PilotAttemptStatus
    completed_at: datetime
    wall_clock_ms: int = Field(ge=0)
    gpu_active_ms: int | None = Field(default=None, ge=0)
    peak_vram_mib: int | None = Field(default=None, ge=0)
    peak_system_ram_mib: int | None = Field(default=None, ge=0)
    average_gpu_temperature_c: Decimal | None = None
    peak_gpu_temperature_c: Decimal | None = None
    average_gpu_power_w: Decimal | None = None
    peak_gpu_power_w: Decimal | None = None
    output_asset_id: UUID | None = None
    external_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    failure_code: str | None = Field(default=None, max_length=200)
    failure_message: str | None = Field(default=None, max_length=5000)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_terminal_result(self) -> "PilotAttemptCompleteRequest":
        if self.status == PilotAttemptStatus.RUNNING:
            raise ValueError("completion status must be terminal")
        if self.status == PilotAttemptStatus.SUCCEEDED and self.output_asset_id is None:
            raise ValueError("output_asset_id is required for succeeded attempts")
        if self.status == PilotAttemptStatus.FAILED and not self.failure_code:
            raise ValueError("failure_code is required for failed attempts")
        return self


class PilotAttemptReviewRequest(BaseModel):
    decision: PilotReviewDecision
    motion_quality: Decimal = Field(ge=0, le=100)
    reference_consistency: Decimal = Field(ge=0, le=100)
    artifact_control: Decimal = Field(ge=0, le=100)
    composition_quality: Decimal = Field(ge=0, le=100)
    defect_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    notes: str = Field(min_length=3, max_length=5000)

    @field_validator("defect_tags")
    @classmethod
    def normalize_defects(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip().lower() for item in value if str(item).strip()}))
