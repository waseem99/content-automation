from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class DeliveryPrivacy(StrEnum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


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
    primary_adapter_key: str = Field(min_length=2, max_length=120)
    fallback_adapter_key: str | None = Field(default=None, min_length=2, max_length=120)
    supported_privacy: tuple[DeliveryPrivacy, ...] = Field(min_length=1, max_length=3)
    default_privacy: DeliveryPrivacy
    credential_secret_ref: str | None = Field(default=None, max_length=500)
    simulated: bool = False
    execution_enabled: bool = False
    requests_per_minute: int = Field(default=30, ge=1, le=10_000)
    requests_per_day: int = Field(default=1000, ge=1, le=1_000_000)
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

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())

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
        return self


class DeliveryCreateRequest(BaseModel):
    final_release_id: UUID
    target_id: UUID
    privacy: DeliveryPrivacy | None = None
    scheduled_for: datetime | None = None
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
