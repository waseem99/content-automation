from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from src.domain.base import FrozenRecord


class StoragePurpose(StrEnum):
    ASSET = "asset"
    RIGHTS_EVIDENCE = "rights_evidence"
    OUTPUT = "output"
    TEMP = "temp"


class AccessLevel(StrEnum):
    PUBLIC_READ = "public_read"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    TEMPORARY = "temporary"


class StorageObject(FrozenRecord):
    uri: str
    purpose: StoragePurpose
    path: Path
    size_bytes: int = Field(ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignedUrlRequest(FrozenRecord):
    uri: str
    purpose: StoragePurpose
    access_level: AccessLevel
    expires_in_seconds: int = Field(default=900, gt=0, le=86_400)


class SignedUrlResult(FrozenRecord):
    url: str
    expires_at: datetime
    access_level: AccessLevel
    purpose: StoragePurpose


class TempFileRecord(FrozenRecord):
    path: Path
    uri: str
    purpose: StoragePurpose = StoragePurpose.TEMP
    expires_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class CleanupSummary(FrozenRecord):
    scanned: int
    deleted: int
    skipped: int
    deleted_paths: tuple[str, ...]


def expires_after(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)
