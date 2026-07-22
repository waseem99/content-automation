from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class OperationsEnvironment(StrEnum):
    STAGING = "staging"
    PRODUCTION = "production"


class OperationsReleaseStatus(StrEnum):
    PLANNED = "planned"
    DEPLOYING = "deploying"
    HEALTHY = "healthy"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    RETIRED = "retired"


class OperationsDrillKind(StrEnum):
    STAGING_RECREATE = "staging_recreate"
    DATABASE_RESTORE = "database_restore"
    ARTIFACT_RESTORE = "artifact_restore"
    WORKER_RESTART = "worker_restart"
    RELEASE_ROLLBACK = "release_rollback"
    API_HEALTH_ALERT = "api_health_alert"
    QUEUE_STALL_ALERT = "queue_stall_alert"
    WORKER_FAILURE_ALERT = "worker_failure_alert"
    LOW_STORAGE_ALERT = "low_storage_alert"
    SECURITY_SCAN = "security_scan"
    RUNBOOK_VALIDATION = "runbook_validation"


class OperationsDrillStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class OperationsAlertKind(StrEnum):
    API_UNHEALTHY = "api_unhealthy"
    QUEUE_STALLED = "queue_stalled"
    WORKER_FAILED = "worker_failed"
    STORAGE_LOW = "storage_low"
    BUDGET_THRESHOLD = "budget_threshold"
    BACKUP_STALE = "backup_stale"
    RESTORE_FAILED = "restore_failed"
    SECURITY_SCAN_FAILED = "security_scan_failed"


class OperationsAlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReleaseRecordRequest(BaseModel):
    environment: OperationsEnvironment
    release_key: str = Field(min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    migration_head: str = Field(min_length=8, max_length=200)
    previous_release_id: UUID | None = None

    @field_validator("release_key", "migration_head", mode="before")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class BackupSetRequest(BaseModel):
    environment: OperationsEnvironment
    backup_key: str = Field(min_length=8, max_length=240, pattern=r"^[A-Za-z0-9._:-]+$")
    database_object_ref: str = Field(min_length=3, max_length=1000)
    artifact_object_ref: str = Field(min_length=3, max_length=1000)
    database_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    migration_head: str = Field(min_length=8, max_length=200)
    database_bytes: int = Field(gt=0)
    artifact_bytes: int = Field(ge=0)
    retention_until: datetime

    @field_validator(
        "backup_key",
        "database_object_ref",
        "artifact_object_ref",
        "migration_head",
        mode="before",
    )
    @classmethod
    def normalize_ref(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def reject_secret_material(self) -> "BackupSetRequest":
        combined = f"{self.database_object_ref}\n{self.artifact_object_ref}".lower()
        if any(marker in combined for marker in ("password=", "secret=", "token=", "api_key=", "api-key=")):
            raise ValueError("backup object references must not contain secret material")
        if self.retention_until.tzinfo is None or self.retention_until.utcoffset() is None:
            raise ValueError("retention_until must include an explicit time zone")
        return self


class DrillStartRequest(BaseModel):
    environment: OperationsEnvironment
    drill_kind: OperationsDrillKind
    release_id: UUID | None = None
    backup_set_id: UUID | None = None


class DrillCompleteRequest(BaseModel):
    status: OperationsDrillStatus
    evidence: dict[str, Any]

    @model_validator(mode="after")
    def require_evidence(self) -> "DrillCompleteRequest":
        if not self.evidence:
            raise ValueError("drill completion evidence cannot be empty")
        return self


class RestoreEvidenceRequest(BaseModel):
    backup_set_id: UUID
    environment: OperationsEnvironment
    database_restored: bool
    artifacts_restored: bool
    migration_head_verified: bool
    database_sha256_verified: bool
    artifact_sha256_verified: bool
    verification: dict[str, Any]

    @model_validator(mode="after")
    def require_complete_restore(self) -> "RestoreEvidenceRequest":
        checks = (
            self.database_restored,
            self.artifacts_restored,
            self.migration_head_verified,
            self.database_sha256_verified,
            self.artifact_sha256_verified,
        )
        if not all(checks) or not self.verification:
            raise ValueError("restore evidence requires every database, artifact, migration, and checksum check")
        return self


class MonitorThresholds(BaseModel):
    queue_stall_seconds: int = Field(default=900, ge=30, le=86400)
    failure_window_seconds: int = Field(default=3600, ge=60, le=7 * 86400)
    failure_rate_warning: float = Field(default=0.10, ge=0, le=1)
    failure_rate_critical: float = Field(default=0.25, ge=0, le=1)
    job_duration_warning_seconds: float = Field(default=900, ge=1)
    storage_warning_free_ratio: float = Field(default=0.20, ge=0, le=1)
    storage_critical_free_ratio: float = Field(default=0.10, ge=0, le=1)
    budget_warning_ratio: float = Field(default=0.80, ge=0, le=2)
    budget_critical_ratio: float = Field(default=1.00, ge=0, le=2)
    backup_stale_seconds: int = Field(default=86400, ge=60, le=30 * 86400)

    @model_validator(mode="after")
    def validate_ordering(self) -> "MonitorThresholds":
        if self.failure_rate_critical < self.failure_rate_warning:
            raise ValueError("critical failure rate cannot be below warning rate")
        if self.storage_critical_free_ratio > self.storage_warning_free_ratio:
            raise ValueError("critical free-storage ratio cannot exceed warning ratio")
        if self.budget_critical_ratio < self.budget_warning_ratio:
            raise ValueError("critical budget ratio cannot be below warning ratio")
        return self
