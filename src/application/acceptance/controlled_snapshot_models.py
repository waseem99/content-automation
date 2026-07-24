from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PilotEvidenceSnapshotRequest(BaseModel):
    bootstrap_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    controlled_start_event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runbook_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at: datetime

    @field_validator(
        "bootstrap_request_sha256",
        "controlled_start_event_sha256",
        "runbook_sha256",
        "snapshot_sha256",
        mode="before",
    )
    @classmethod
    def normalize_digest(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("started_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")
        return value


__all__ = ["PilotEvidenceSnapshotRequest"]
