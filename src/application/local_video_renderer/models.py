from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class LocalVideoProfile(StrEnum):
    DRAFT = "draft"
    SELECTED_FINAL = "selected_final"
    TRANSITION = "transition"
    START_END_FRAME = "start_end_frame"
    UPSCALE = "upscale"


class LocalVideoPreflightRequest(BaseModel):
    portfolio_content_id: UUID
    content_version: int = Field(ge=1)
    pilot_case_id: UUID | None = None
    workflow_key: str = Field(min_length=2, max_length=200)
    workflow_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    distribution_scope: str = Field(pattern=r"^(internal|territory_limited|global_public)$")
    release_territories: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    width: int = Field(ge=256, le=8192)
    height: int = Field(ge=256, le=8192)
    fps: int = Field(default=24, ge=1, le=240)
    frame_count: int = Field(ge=1, le=10000)
    inference_steps: int = Field(ge=1, le=500)
    seed: int
    prompt: str = Field(min_length=3, max_length=20000)
    negative_prompt: str | None = Field(default=None, max_length=10000)
    input_asset_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=20)
    request_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("release_territories")
    @classmethod
    def normalize_territories(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))

    @model_validator(mode="after")
    def validate_scope(self) -> "LocalVideoPreflightRequest":
        if self.distribution_scope == "territory_limited" and not self.release_territories:
            raise ValueError("release_territories are required for territory_limited rendering")
        return self


class LocalVideoAttemptResult(BaseModel):
    preflight_id: UUID
    generation_job_id: UUID
    output_asset_id: UUID
    preview_asset_id: UUID | None = None
    wall_clock_ms: int = Field(ge=0)
    gpu_active_ms: int | None = Field(default=None, ge=0)
    peak_vram_mib: int | None = Field(default=None, ge=0)
    average_gpu_temperature_c: Decimal | None = None
    peak_gpu_temperature_c: Decimal | None = None
    average_gpu_power_w: Decimal | None = None
    peak_gpu_power_w: Decimal | None = None
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    external_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def local_only(self) -> "LocalVideoAttemptResult":
        if self.external_cost_usd != 0:
            raise ValueError("local renderer attempts must record external_cost_usd=0")
        return self
