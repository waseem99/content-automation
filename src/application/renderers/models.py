from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class RendererOperation(StrEnum):
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"
    VIDEO_TO_VIDEO = "video_to_video"
    UPSCALE = "upscale"


class RendererStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class RendererHealth(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class RendererAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RendererCatalogueCreate(BaseModel):
    renderer_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    display_name: str = Field(min_length=3, max_length=200)
    adapter_key: str = Field(min_length=2, max_length=120)
    operation: RendererOperation
    output_formats: tuple[str, ...] = Field(min_length=1, max_length=20)
    min_duration_seconds: Decimal = Field(default=Decimal("0"), ge=0, le=86400)
    max_duration_seconds: Decimal = Field(gt=0, le=86400)
    max_width: int = Field(ge=64, le=16384)
    max_height: int = Field(ge=64, le=16384)
    capabilities: tuple[str, ...] = Field(default=(), max_length=100)
    expected_seconds_base: Decimal = Field(default=Decimal("0"), ge=0, le=86400)
    expected_seconds_per_second: Decimal = Field(default=Decimal("0"), ge=0, le=86400)
    base_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    cost_per_second_usd: Decimal = Field(default=Decimal("0"), ge=0)
    usage_evidence: dict[str, Any] = Field(default_factory=dict)
    health: RendererHealth = RendererHealth.UNKNOWN
    quality_rating: Decimal = Field(default=Decimal("0"), ge=0, le=5)
    simulated: bool = False
    execution_enabled: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("renderer_key", "adapter_key", mode="before")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("output_formats", mode="before")
    @classmethod
    def normalize_output_formats(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    str(value).strip().lower().lstrip(".")
                    for value in values
                    if str(value).strip().lstrip(".")
                }
            )
        )

    @field_validator("capabilities", mode="before")
    @classmethod
    def normalize_capability_set(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({str(value).strip().lower() for value in values if str(value).strip()}))

    @model_validator(mode="after")
    def validate_ranges_and_execution(self) -> "RendererCatalogueCreate":
        if self.max_duration_seconds < self.min_duration_seconds:
            raise ValueError("max_duration_seconds must be greater than or equal to min_duration_seconds")
        if self.execution_enabled and not self.simulated:
            raise ValueError("P93 only permits execution for simulated renderer entries")
        if self.simulated and self.adapter_key != "simulated":
            raise ValueError("simulated renderer entries must use the simulated adapter")
        return self


class RendererRepriceRequest(BaseModel):
    base_cost_usd: Decimal = Field(ge=0)
    cost_per_second_usd: Decimal = Field(ge=0)
    reason: str = Field(min_length=3, max_length=1000)


class RendererHealthUpdate(BaseModel):
    health: RendererHealth
    quality_rating: Decimal = Field(ge=0, le=5)
    usage_evidence: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=3, max_length=1000)


class RendererSupportRequest(BaseModel):
    operation: RendererOperation
    output_format: str = Field(min_length=2, max_length=40)
    duration_seconds: Decimal = Field(gt=0, le=86400)
    width: int = Field(ge=64, le=16384)
    height: int = Field(ge=64, le=16384)
    required_capabilities: tuple[str, ...] = Field(default=(), max_length=100)

    @field_validator("output_format", mode="before")
    @classmethod
    def normalize_format(cls, value: str) -> str:
        return value.strip().lower().lstrip(".")

    @field_validator("required_capabilities", mode="before")
    @classmethod
    def normalize_capabilities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({str(value).strip().lower() for value in values if str(value).strip()}))


class RendererResolveRequest(RendererSupportRequest):
    renderer_key: str | None = Field(default=None, min_length=3, max_length=120)

    @field_validator("renderer_key", mode="before")
    @classmethod
    def normalize_optional_key(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None


class RendererSubmissionRequest(BaseModel):
    renderer_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=240)
    request: RendererSupportRequest
    input_payload: dict[str, Any]

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be blank")
        return normalized

    @model_validator(mode="after")
    def require_input(self) -> "RendererSubmissionRequest":
        if not self.input_payload:
            raise ValueError("input_payload cannot be empty")
        return self


class RendererAdapterResult(BaseModel):
    provider_request_id: str = Field(min_length=1, max_length=240)
    output_payload: dict[str, Any]
    actual_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def require_output(self) -> "RendererAdapterResult":
        if not self.output_payload:
            raise ValueError("output_payload cannot be empty")
        return self


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def quantize_seconds(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
