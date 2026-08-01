from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


ALLOWED_PLATFORMS = (
    "facebook",
    "instagram",
    "tiktok",
    "youtube",
    "youtube_shorts",
)

DEFAULT_AUTOMATIC_STAGES = (
    "concept",
    "script",
    "sources",
    "narration_plan",
    "scene_plan",
    "caption_package",
    "final_generation_package",
)

DEFAULT_HARD_BLOCK_CODES = (
    "rights_block",
    "safety_block",
    "territory_block",
    "structural_block",
    "source_block",
    "budget_block",
    "system_block",
)


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CampaignVersionStatus(StrEnum):
    DRAFT = "draft"
    INVALID = "invalid"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class CampaignItemState(StrEnum):
    DRAFT = "draft"
    VALID = "valid"
    INVALID = "invalid"
    ACTIVATED = "activated"
    AUTO_PROGRESSING = "auto_progressing"
    HUMAN_EXCEPTION = "human_exception"
    HARD_BLOCK = "hard_block"
    READY_FOR_FINAL_VIDEO_GENERATION = "ready_for_final_video_generation"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class CampaignCreateRequest(BaseModel):
    campaign_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    brand_id: UUID
    name: str = Field(min_length=3, max_length=240)
    description: str = Field(default="", max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("campaign_key", "name", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class AutopilotPolicyCreateRequest(BaseModel):
    policy_key: str = Field(default="default-autopilot", min_length=3, max_length=120)
    minimum_auto_score: float = Field(default=70.0, ge=0, le=100)
    max_auto_corrections: int = Field(default=2, ge=0, le=10)
    automatic_stages: tuple[str, ...] = DEFAULT_AUTOMATIC_STAGES
    hard_block_codes: tuple[str, ...] = DEFAULT_HARD_BLOCK_CODES
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("policy_key")
    @classmethod
    def normalize_policy_key(cls, value: str) -> str:
        return value.strip()

    @field_validator("automatic_stages", "hard_block_codes")
    @classmethod
    def normalize_unique_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
        if not normalized:
            raise ValueError("at least one value is required")
        return normalized


class CampaignItemInput(BaseModel):
    item_key: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    title: str = Field(min_length=3, max_length=240)
    topic: str = Field(min_length=3, max_length=3000)
    objective: str = Field(default="", max_length=2000)
    audience: str = Field(default="", max_length=1000)
    format_name: str = Field(default="master_video", min_length=2, max_length=80)
    primary_platform: str = Field(default="facebook")
    target_platforms: tuple[str, ...] = ("facebook",)
    target_duration_seconds: int = Field(default=120, ge=10, le=150)
    short_cut_count: int = Field(default=0, ge=0, le=2)
    language: str = Field(default="en-US", min_length=2, max_length=40)
    scheduled_for: date
    priority: int = Field(default=50, ge=-1000, le=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "item_key",
        "title",
        "topic",
        "objective",
        "audience",
        "format_name",
        "primary_platform",
        "language",
    )
    @classmethod
    def normalize_item_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("primary_platform")
    @classmethod
    def validate_primary_platform(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in ALLOWED_PLATFORMS:
            raise ValueError("unsupported primary platform")
        return normalized

    @field_validator("target_platforms")
    @classmethod
    def normalize_target_platforms(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(str(value).strip().lower() for value in values if str(value).strip()))
        if not normalized:
            raise ValueError("at least one target platform is required")
        unsupported = sorted(set(normalized) - set(ALLOWED_PLATFORMS))
        if unsupported:
            raise ValueError("unsupported target platforms: " + ", ".join(unsupported))
        return normalized

    @model_validator(mode="after")
    def include_primary_platform(self) -> "CampaignItemInput":
        if self.primary_platform not in self.target_platforms:
            self.target_platforms = (self.primary_platform, *self.target_platforms)
        return self


class CampaignItemsAddRequest(BaseModel):
    items: list[CampaignItemInput] = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def unique_item_keys(self) -> "CampaignItemsAddRequest":
        keys = [item.item_key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("item_key values must be unique within one request")
        return self
