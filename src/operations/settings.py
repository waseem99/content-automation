from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OperationsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPS_",
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = Field(default="staging", pattern=r"^(staging|production)$")
    service_name: str = Field(default="content-automation", min_length=3, max_length=120)
    release_key: str = Field(default="local-unreleased", min_length=8, max_length=200)
    git_sha: str = Field(default="0" * 40, pattern=r"^[0-9a-f]{40}$")
    image_digest: str = Field(default="sha256:" + "0" * 64, pattern=r"^sha256:[0-9a-f]{64}$")
    configuration_digest: str = Field(default="0" * 64, pattern=r"^[0-9a-f]{64}$")
    migration_head: str = Field(default="unmigrated", min_length=8, max_length=200)
    structured_logs: bool = True
    max_request_body_bytes: int = Field(default=8 * 1024 * 1024, ge=1024, le=1024 * 1024 * 1024)
    requests_per_minute: int = Field(default=120, ge=1, le=100_000)
    rate_limit_exempt_paths: tuple[str, ...] = ("/health", "/runtime/ready")
    storage_capacity_bytes: int = Field(default=50 * 1024 * 1024 * 1024, gt=0)
    backup_directory: Path = Path(".runtime/backups")
    backup_retention_days: int = Field(default=14, ge=1, le=3650)
    allow_destructive_restore_drill: bool = False

    @field_validator("service_name", "release_key", "migration_head", mode="before")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("rate_limit_exempt_paths", mode="before")
    @classmethod
    def normalize_paths(cls, values) -> tuple[str, ...]:
        if isinstance(values, str):
            values = [item.strip() for item in values.split(",") if item.strip()]
        return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))

    @model_validator(mode="after")
    def production_safety(self) -> "OperationsSettings":
        if self.environment == "production":
            placeholders = {
                "release_key": self.release_key == "local-unreleased",
                "git_sha": self.git_sha == "0" * 40,
                "image_digest": self.image_digest == "sha256:" + "0" * 64,
                "configuration_digest": self.configuration_digest == "0" * 64,
                "migration_head": self.migration_head == "unmigrated",
            }
            invalid = sorted(key for key, value in placeholders.items() if value)
            if invalid:
                raise ValueError(
                    "production operations settings require non-placeholder release identity: "
                    + ", ".join(invalid)
                )
            if self.allow_destructive_restore_drill:
                raise ValueError("destructive restore drills cannot be enabled in production")
        return self

    def public_snapshot(self) -> dict[str, object]:
        return {
            "environment": self.environment,
            "service_name": self.service_name,
            "release_key": self.release_key,
            "git_sha": self.git_sha,
            "image_digest": self.image_digest,
            "configuration_digest": self.configuration_digest,
            "migration_head": self.migration_head,
            "structured_logs": self.structured_logs,
            "max_request_body_bytes": self.max_request_body_bytes,
            "requests_per_minute": self.requests_per_minute,
            "rate_limit_exempt_paths": list(self.rate_limit_exempt_paths),
            "storage_capacity_bytes": self.storage_capacity_bytes,
            "backup_retention_days": self.backup_retention_days,
            "allow_destructive_restore_drill": self.allow_destructive_restore_drill,
        }


@lru_cache(maxsize=1)
def get_operations_settings() -> OperationsSettings:
    return OperationsSettings()
