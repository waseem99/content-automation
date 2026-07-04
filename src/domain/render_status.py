from enum import StrEnum


class RenderMode(StrEnum):
    PREVIEW = "preview"
    PUBLISH = "publish"


class RenderJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
