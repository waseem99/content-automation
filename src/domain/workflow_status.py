from enum import StrEnum


class WorkflowStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVISION = "needs_revision"
    AWAITING_HUMAN = "awaiting_human"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    SUPERSEDED = "superseded"


class ProviderCallStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
