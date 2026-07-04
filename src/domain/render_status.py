from enum import StrEnum


class RenderMode(StrEnum):
    PREVIEW = "preview"
    PUBLISH = "publish"


class RenderManifestStatus(StrEnum):
    DRAFT = "draft"
    SEALED = "sealed"
    APPROVED = "approved"


class RenderJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ManifestAssetRole(StrEnum):
    SOURCE_VIDEO = "source_video"
    CLIP = "clip"
    IMAGE = "image"
    VOICE = "voice"
    MUSIC = "music"
    FONT = "font"
    LOGO = "logo"
    OVERLAY = "overlay"
    OTHER = "other"
