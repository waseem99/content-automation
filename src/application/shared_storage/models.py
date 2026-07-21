from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SharedStorageDriver(StrEnum):
    LOCAL = "local"
    S3_COMPATIBLE = "s3_compatible"


class SharedStorageEnvironment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ArtifactObjectRole(StrEnum):
    ORIGINAL = "original"
    REVIEW_PROXY = "review_proxy"
    THUMBNAIL = "thumbnail"


class ArtifactKind(StrEnum):
    SOURCE = "source"
    VOICEOVER = "voiceover"
    KEYFRAME = "keyframe"
    PREVIEW = "preview"
    PREMIUM_CLIP = "premium_clip"
    THUMBNAIL = "thumbnail"
    FINAL_VIDEO = "final_video"
    PACKAGE = "package"
    REFERENCE = "reference"
    EVIDENCE = "evidence"
    OTHER = "other"


class StorageBackendRequest(BaseModel):
    backend_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    display_name: str = Field(min_length=2, max_length=200)
    driver: SharedStorageDriver
    environment: SharedStorageEnvironment
    endpoint_url: str | None = Field(default=None, max_length=2000)
    bucket_name: str | None = Field(default=None, max_length=300)
    base_prefix: str = Field(default="", max_length=500)
    region: str | None = Field(default=None, max_length=100)
    credential_secret_ref: str | None = Field(default=None, max_length=500)
    public_base_url: str | None = Field(default=None, max_length=2000)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_driver(self) -> "StorageBackendRequest":
        if self.driver == SharedStorageDriver.S3_COMPATIBLE:
            if not self.bucket_name or not self.credential_secret_ref:
                raise ValueError("S3-compatible backends require bucket_name and credential_secret_ref")
        if self.credential_secret_ref and any(
            marker in self.credential_secret_ref.lower()
            for marker in ("password=", "secret=", "token=", "key=")
        ):
            raise ValueError("credential_secret_ref must be a reference, not secret material")
        return self


class SharedObjectResult(BaseModel):
    object_key: str
    storage_uri: str
    object_version: str | None = None
    etag: str | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    mime_type: str | None = None
    local_path: Path | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactVersionRequest(BaseModel):
    brand_id: UUID
    portfolio_content_id: UUID | None = None
    content_version: int | None = Field(default=None, ge=1)
    artifact_key: str = Field(min_length=2, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]+$")
    artifact_kind: ArtifactKind
    original_asset_id: UUID
    review_proxy_asset_id: UUID | None = None
    thumbnail_asset_id: UUID | None = None
    backend_id: UUID
    parent_version_id: UUID | None = None
    retention_until: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content_pair(self) -> "ArtifactVersionRequest":
        if self.portfolio_content_id is None and self.content_version is not None:
            raise ValueError("content_version requires portfolio_content_id")
        return self


class SignedAccessRequest(BaseModel):
    role: ArtifactObjectRole = ArtifactObjectRole.REVIEW_PROXY
    expires_in_seconds: int = Field(default=900, ge=30, le=86_400)
    issued_to_operator_id: str | None = Field(default=None, max_length=200)
    access_purpose: str = Field(default="review", pattern=r"^(review|download|restore_verification)$")


class SignedAccessResult(BaseModel):
    grant_id: UUID
    url: str
    expires_at: datetime
    artifact_version_id: UUID
    storage_object_id: UUID
    role: ArtifactObjectRole


class LegalHoldRequest(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def require_reason(self) -> "LegalHoldRequest":
        if self.enabled and (not self.reason or len(self.reason.strip()) < 3):
            raise ValueError("legal hold requires a reason")
        return self


class DeletionRequest(BaseModel):
    rationale: str = Field(min_length=3, max_length=5000)


class BackupPrepareRequest(BaseModel):
    backend_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestoreVerifyRequest(BaseModel):
    restored_backend_key: str = Field(min_length=2, max_length=100)
    verifier_label: str = Field(min_length=2, max_length=200)
