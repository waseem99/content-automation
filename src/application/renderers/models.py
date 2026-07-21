from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class RendererOperation(StrEnum):
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"
    VIDEO_TO_VIDEO = "video_to_video"
    LIP_SYNC = "lip_sync"
    VIDEO_EDIT = "video_edit"


class RendererAdapterKind(StrEnum):
    SIMULATED = "simulated"
    HTTP_API = "http_api"
    MANAGED_SDK = "managed_sdk"


class RendererStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class RendererHealth(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class RendererEntryRequest(BaseModel):
    provider_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    provider_display_name: str = Field(min_length=2, max_length=200)
    model_key: str = Field(min_length=1, max_length=200)
    model_display_name: str = Field(min_length=2, max_length=200)
    operation: RendererOperation
    adapter_kind: RendererAdapterKind
    supported_formats: tuple[str, ...] = Field(min_length=1, max_length=30)
    min_duration_seconds: Decimal = Field(gt=0)
    max_duration_seconds: Decimal = Field(gt=0)
    duration_step_seconds: Decimal | None = Field(default=None, gt=0)
    supported_resolutions: tuple[dict[str, int], ...] = Field(min_length=1, max_length=30)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    expected_latency_seconds: dict[str, int] = Field(default_factory=dict)
    pricing: dict[str, Decimal | int | float] = Field(default_factory=dict)
    pricing_currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    quality_rating: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    commercial_use_allowed: bool = False
    usage_terms_url: str | None = Field(default=None, max_length=2000)
    usage_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    usage_evidence_recorded_at: datetime
    data_handling: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=5000)
    parent_entry_id: UUID | None = None

    @field_validator("supported_formats")
    @classmethod
    def normalize_formats(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({item.strip().lower() for item in value if item.strip()}))
        if not normalized:
            raise ValueError("supported_formats cannot be empty")
        return normalized

    @field_validator("supported_resolutions")
    @classmethod
    def validate_resolutions(cls, value: tuple[dict[str, int], ...]) -> tuple[dict[str, int], ...]:
        seen: set[tuple[int, int]] = set()
        normalized: list[dict[str, int]] = []
        for item in value:
            width = int(item.get("width", 0))
            height = int(item.get("height", 0))
            if not 256 <= width <= 8192 or not 256 <= height <= 8192:
                raise ValueError("renderer resolutions must be between 256 and 8192 pixels")
            pair = (width, height)
            if pair not in seen:
                seen.add(pair)
                normalized.append({"width": width, "height": height})
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_bounds_and_adapter(self) -> "RendererEntryRequest":
        if self.max_duration_seconds < self.min_duration_seconds:
            raise ValueError("max_duration_seconds must be at least min_duration_seconds")
        if self.adapter_kind == RendererAdapterKind.SIMULATED and self.provider_key != "simulated":
            raise ValueError("simulated adapters must use provider_key=simulated")
        return self


class RendererRepriceRequest(BaseModel):
    pricing: dict[str, Decimal | int | float]
    expected_latency_seconds: dict[str, int] | None = None
    quality_rating: Decimal | None = Field(default=None, ge=0, le=100)
    usage_evidence_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    usage_evidence_recorded_at: datetime | None = None
    rationale: str = Field(min_length=3, max_length=5000)
    activate: bool = True


class RendererHealthRequest(BaseModel):
    status: RendererHealth
    latency_ms: int | None = Field(default=None, ge=0)
    checked_by: str = Field(min_length=1, max_length=200)
    details: dict[str, Any] = Field(default_factory=dict)


class RendererCapabilityRequest(BaseModel):
    portfolio_content_id: UUID
    content_version: int = Field(ge=1)
    operation: RendererOperation
    format: str = Field(min_length=1, max_length=100)
    duration_seconds: Decimal = Field(gt=0)
    width: int = Field(ge=256, le=8192)
    height: int = Field(ge=256, le=8192)
    fps: int = Field(default=24, ge=1, le=240)
    required_capabilities: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    input_asset_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=50)
    renderer_catalogue_entry_id: UUID | None = None
    provider_key: str | None = Field(default=None, max_length=100)
    model_key: str | None = Field(default=None, max_length=200)
    request_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("format")
    @classmethod
    def normalize_format(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("required_capabilities")
    @classmethod
    def normalize_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({item.strip() for item in value if item.strip()}))

    @model_validator(mode="after")
    def validate_selector(self) -> "RendererCapabilityRequest":
        if self.renderer_catalogue_entry_id is not None and (self.provider_key or self.model_key):
            raise ValueError("select by entry id or provider/model, not both")
        return self


class SimulatedJobRequest(BaseModel):
    renderer_preflight_id: UUID
    production_workflow_id: UUID | None = None
    production_workflow_version_id: UUID | None = None
    preferred_worker_id: str | None = Field(default=None, max_length=200)
    priority: int = Field(default=0, ge=-1000, le=1000)
    timeout_seconds: int = Field(default=300, ge=5, le=86400)
    max_attempts: int = Field(default=2, ge=1, le=10)

    @model_validator(mode="after")
    def workflow_pair(self) -> "SimulatedJobRequest":
        if self.production_workflow_version_id is not None and self.production_workflow_id is None:
            raise ValueError("production_workflow_id is required with production_workflow_version_id")
        return self
