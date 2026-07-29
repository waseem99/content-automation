from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class LocalVideoOperation(StrEnum):
    IMAGE_TO_VIDEO = "image_to_video"
    START_END_FRAME = "start_end_frame"
    VIDEO_UPSCALE = "video_upscale"


class LocalVideoRequest(BaseModel):
    generation_job_id: UUID
    workflow_version_id: UUID
    model_policy_id: UUID
    operation: LocalVideoOperation
    source_path: Path
    end_path: Path | None = None
    prompt: str = Field(min_length=3, max_length=10000)
    negative_prompt: str | None = Field(default=None, max_length=5000)
    seed: int
    width: int = Field(ge=256, le=4096)
    height: int = Field(ge=256, le=4096)
    fps: int = Field(ge=1, le=60)
    frame_count: int = Field(ge=1, le=1000)
    inference_steps: int = Field(ge=1, le=200)
    timeout_seconds: int = Field(default=3600, ge=30, le=86400)
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_path", "end_path")
    @classmethod
    def require_absolute_paths(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("local video media paths must be absolute")
        return value

    @model_validator(mode="after")
    def validate_operation_inputs(self) -> "LocalVideoRequest":
        if self.operation == LocalVideoOperation.START_END_FRAME and self.end_path is None:
            raise ValueError("end_path is required for start_end_frame")
        if self.operation != LocalVideoOperation.START_END_FRAME and self.end_path is not None:
            raise ValueError("end_path is only allowed for start_end_frame")
        if self.frame_count < self.fps:
            raise ValueError("local video clips must be at least one second")
        return self


class LocalVideoResult(BaseModel):
    provider_request_id: str = Field(min_length=1, max_length=240)
    output_path: Path
    preview_path: Path | None = None
    workflow_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    wall_clock_ms: int = Field(ge=0)
    external_fee_usd: int = Field(default=0, ge=0, le=0)
    metrics: dict[str, Any] = Field(default_factory=dict)
