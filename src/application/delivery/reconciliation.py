from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class DeliveryPlatformStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    DELETED = "deleted"
    UNKNOWN = "unknown"


class DeliveryReconciliationResult(BaseModel):
    platform_status: DeliveryPlatformStatus
    response_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_response_evidence(self) -> "DeliveryReconciliationResult":
        if not self.response_payload:
            raise ValueError("reconciliation response_payload cannot be empty")
        return self
