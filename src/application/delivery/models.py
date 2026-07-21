from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator


class DeliveryPrivacy(StrEnum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class DeliveryMode(StrEnum):
    DRAFT = "draft"
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"


class DeliveryTargetStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    RETIRED = "retired"


class DeliveryStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryTransport(StrEnum):
    PRIMARY = "primary"
    FALLBACK = "fallback"


class DeliveryTargetRequest(BaseModel):
    target_key: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    display_name: str = Field(min_length=3, max_length=200)
    platform: str = Field(min_length=2, max_length=80)
    environment: str = Field(pattern=r"^(test|staging|production)$")
    target_account_ref: str = Field(min_length=3, max_length=240)
    time_zone: str = Field(min_length=1, max_length=100)
    primary_adapter_key: str = Field(min_length=2, max_length=120)
    fallback_adapter_key: str | None = Field(default=None, min_length=2, max_length=120)
    supported_privacy: tuple[DeliveryPrivacy, ...] = Field(min_length=1, max_length=3)
    default_privacy: DeliveryPrivacy
    credential_secret_ref: str | None = Field(default=None, max_length=500)
    simulated: bool = False
    execution_enabled: bool = False
    requests_per_minute: int = Field(default=30, ge=1, le=10_000)
    requests_per_day: int = Field(default=1000, ge=1, le=1_000_000)
    title_max_length: int = Field(default=100, ge=1, le=1000)
    caption_max_length: int = Field(default=2200, ge=1, le=20_000)
    hashtag_limit: int = Field(default=30, ge=0, le=100)
    thumbnail_required: bool = True
    disclosure_required: bool = False
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "target_key",
        "platform",
        "environment",
        "primary_adapter_key",
        "fallback_adapter_key",
        mode="before",
    )
    @classmethod
    def normalize_key(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None

    @field_validator("display_name", "target_account_ref", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("time_zone", mode="before")
    @classmethod
    def validate_time_zone(cls, value: str) -> str:
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("time_zone must be a valid IANA time zone") from exc
        return normalized

    @field_validator("supported_privacy", mode="before")
    @classmethod
    def normalize_privacy(cls, values: tuple[DeliveryPrivacy | str, ...]) -> tuple[DeliveryPrivacy, ...]:
        return tuple(sorted({DeliveryPrivacy(value) for value in values}, key=lambda item: item.value))

    @model_validator(mode="after")
    def validate_execution_boundary(self) -> "DeliveryTargetRequest":
        if self.default_privacy not in self.supported_privacy:
            raise ValueError("default_privacy must be included in supported_privacy")
        if self.requests_per_day < self.requests_per_minute:
            raise ValueError("requests_per_day cannot be lower than requests_per_minute")
        if self.execution_enabled and not self.simulated:
            raise ValueError("P97 only permits execution for simulated delivery targets")
        if self.simulated and not self.primary_adapter_key.startswith("simulated-"):
            raise ValueError("simulated targets must use a simulated primary adapter")
        if self.fallback_adapter_key and self.simulated and not self.fallback_adapter_key.startswith("simulated-"):
            raise ValueError("simulated targets must use a simulated fallback adapter")
        if self.credential_secret_ref and any(
            marker in self.credential_secret_ref.lower()
            for marker in ("password=", "secret=", "token=", "key=")
        ):
            raise ValueError("credential_secret_ref must be a reference, not secret material")
        if any(
            marker in self.target_account_ref.lower()
            for marker in ("password=", "secret=", "token=", "key=")
        ):
            raise ValueError("target_account_ref must identify an account without secret material")
        configuration = dict(self.configuration)
        configuration.update(
            {
                "target_account_ref": self.target_account_ref,
                "time_zone": self.time_zone,
                "content_contract": {
                    "title_max_length": self.title_max_length,
                    "caption_max_length": self.caption_max_length,
                    "hashtag_limit": self.hashtag_limit,
                    "thumbnail_required": self.thumbnail_required,
                    "disclosure_required": self.disclosure_required,
                },
            }
        )
        self.configuration = configuration
        return self


class DeliveryCreateRequest(BaseModel):
    final_release_id: UUID
    target_id: UUID
    delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE
    privacy: DeliveryPrivacy | None = None
    scheduled_for: datetime | None = None
    title: str = Field(min_length=1, max_length=1000)
    caption: str = Field(min_length=1, max_length=20_000)
    hashtags: tuple[str, ...] = Field(default=(), max_length=100)
    thumbnail_artifact_version_id: UUID | None = None
    disclosure_text: str | None = Field(default=None, max_length=5000)
    idempotency_key: str = Field(min_length=8, max_length=240)
    max_attempts: int = Field(default=3, ge=1, le=20)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be blank")
        return normalized

    @field_validator("title", "caption", mode="before")
    @classmethod
    def normalize_copy(cls, value: str) -> str:
        return value.strip()

    @field_validator("disclosure_text", mode="before")
    @classmethod
    def normalize_disclosure(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("hashtags", mode="before")
    @classmethod
    def normalize_hashtags(cls, values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            tag = str(value).strip().lstrip("#")
            if not tag or len(tag) > 100 or not tag.replace("_", "").isalnum():
                raise ValueError("hashtags must contain only letters, numbers, or underscores")
            identity = tag.casefold()
            if identity not in seen:
                normalized.append(tag)
                seen.add(identity)
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_schedule_and_snapshot(self) -> "DeliveryCreateRequest":
        if self.delivery_mode == DeliveryMode.SCHEDULED:
            if self.scheduled_for is None:
                raise ValueError("scheduled delivery requires scheduled_for")
            if self.scheduled_for.tzinfo is None or self.scheduled_for.utcoffset() is None:
                raise ValueError("scheduled_for must include an explicit time zone")
            if self.scheduled_for.astimezone(timezone.utc) <= datetime.now(timezone.utc):
                raise ValueError("scheduled_for must be in the future")
        elif self.scheduled_for is not None:
            raise ValueError("scheduled_for is only valid for scheduled delivery")

        metadata = dict(self.metadata)
        metadata.update(
            {
                "delivery_mode": self.delivery_mode.value,
                "title": self.title,
                "caption": self.caption,
                "hashtags": list(self.hashtags),
                "thumbnail_artifact_version_id": (
                    str(self.thumbnail_artifact_version_id)
                    if self.thumbnail_artifact_version_id is not None
                    else None
                ),
                "disclosure_text": self.disclosure_text,
            }
        )
        self.metadata = metadata
        return self


class DeliveryClaimRequest(BaseModel):
    worker_id: str = Field(min_length=3, max_length=120)
    target_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    lease_seconds: int = Field(default=180, ge=30, le=3600)


class DeliveryExecuteRequest(BaseModel):
    delivery_request_id: UUID
    worker_id: str = Field(min_length=3, max_length=120)
    lease_token: UUID


class DeliveryCancelRequest(BaseModel):
    rationale: str = Field(min_length=3, max_length=5000)


class DeliveryAdapterRequest(BaseModel):
    delivery_request_id: UUID
    delivery_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    platform: str
    target_key: str
    privacy: DeliveryPrivacy
    release_manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_manifest: dict[str, Any]
    output_artifact_version_id: UUID
    output_asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeliveryAdapterResult(BaseModel):
    provider_request_id: str = Field(min_length=1, max_length=500)
    platform_reference: str = Field(min_length=1, max_length=2000)
    response_payload: dict[str, Any]

    @model_validator(mode="after")
    def require_response(self) -> "DeliveryAdapterResult":
        if not self.response_payload:
            raise ValueError("response_payload cannot be empty")
        return self
