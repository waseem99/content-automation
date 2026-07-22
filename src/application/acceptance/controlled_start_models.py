from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PilotControlledStartRequest(BaseModel):
    bootstrap_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runbook_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("bootstrap_request_sha256", "runbook_sha256", mode="before")
    @classmethod
    def normalize_digest(cls, value: str) -> str:
        return value.strip().lower()


__all__ = ["PilotControlledStartRequest"]
