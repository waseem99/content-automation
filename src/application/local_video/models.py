from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from src.application.video_pilot.models import DistributionScope


class LocalVideoProvider(StrEnum):
    WAN = "wan-ai"
    HUNYUAN = "tencent-hunyuan"


class LocalVideoEnqueueRequest(BaseModel):
    portfolio_content_id: UUID
    content_version: int = Field(ge=1)
    input_asset_id: UUID
    pilot_case_id: UUID | None = None
    provider_key: str = Field(default=LocalVideoProvider.WAN.value, min_length=2, max_length=100)
    model_key: str = Field(default="Wan2.2-TI2V-5B", min_length=1, max_length=200)
    distribution_scope: DistributionScope = DistributionScope.GLOBAL_PUBLIC
    release_territories: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    prompt: str = Field(min_length=3, max_length=10000)
    negative_prompt: str = Field(default="", max_length=5000)
    duration_seconds: Decimal = Field(default=Decimal("5"), ge=Decimal("3"), le=Decimal("6"))
    width: int = Field(default=1280, ge=256, le=2048)
    height: int = Field(default=704, ge=256, le=2048)
    fps: int = Field(default=24, ge=1, le=60)
    seed: int = Field(ge=0, le=2**63 - 1)
    inference_steps: int = Field(default=20, ge=1, le=100)
    cfg: Decimal = Field(default=Decimal("5"), ge=Decimal("0"), le=Decimal("30"))
    sampler_name: str = Field(default="uni_pc", min_length=1, max_length=100)
    scheduler: str = Field(default="simple", min_length=1, max_length=100)
    priority: int = Field(default=0, ge=-1000, le=1000)
    timeout_seconds: int = Field(default=3600, ge=60, le=86400)
    max_attempts: int = Field(default=2, ge=1, le=4)
    idempotency_key: str = Field(min_length=8, max_length=240)

    @field_validator("provider_key")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("model_key", "sampler_name", "scheduler", "idempotency_key")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("release_territories")
    @classmethod
    def normalize_territories(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))

    @model_validator(mode="after")
    def validate_distribution_and_frames(self) -> "LocalVideoEnqueueRequest":
        if self.distribution_scope == DistributionScope.TERRITORY_LIMITED and not self.release_territories:
            raise ValueError("release_territories are required for territory_limited clips")
        frame_count = round(float(self.duration_seconds) * self.fps) + 1
        if frame_count < 2 or frame_count > 361:
            raise ValueError("derived frame count must be between 2 and 361")
        return self

    @property
    def frame_count(self) -> int:
        return round(float(self.duration_seconds) * self.fps) + 1


class LocalVideoProfileActivateRequest(BaseModel):
    provider_key: str = Field(min_length=2, max_length=100)
    model_key: str = Field(min_length=1, max_length=200)
    workflow_path: str = Field(min_length=3, max_length=2000)
    workflow_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_files: tuple[dict[str, str], ...] = Field(min_length=1, max_length=20)
    activation_evidence: dict[str, object] = Field(default_factory=dict)

    @field_validator("provider_key")
    @classmethod
    def normalize_activation_provider(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_model_files(self) -> "LocalVideoProfileActivateRequest":
        for item in self.model_files:
            if not item.get("role") or not item.get("relative_path"):
                raise ValueError("each model file requires role and relative_path")
            digest = item.get("sha256") or ""
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise ValueError("each model file requires a lowercase SHA-256 digest")
        return self
