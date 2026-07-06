from __future__ import annotations

import mimetypes
from pathlib import Path

from pydantic import Field

from src.application.assets.hashing import inspect_file
from src.domain.base import FrozenRecord


class UploadValidationError(RuntimeError):
    pass


class UploadValidationPolicy(FrozenRecord):
    allowed_mime_types: tuple[str, ...] = ("image/png", "image/jpeg", "video/mp4", "audio/mpeg", "audio/wav", "application/pdf")
    allowed_extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".mp4", ".mp3", ".wav", ".pdf")
    max_size_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    require_probe: bool = False


class UploadValidationResult(FrozenRecord):
    path: Path
    sha256: str
    size_bytes: int
    mime_type: str
    extension: str


class MediaUploadValidator:
    def __init__(self, policy: UploadValidationPolicy | None = None) -> None:
        self.policy = policy or UploadValidationPolicy()

    def validate(self, path: Path) -> UploadValidationResult:
        inspection = inspect_file(path)
        extension = inspection.path.suffix.lower()
        guessed_mime = inspection.mime_type or mimetypes.guess_type(inspection.path.name)[0]
        if inspection.size_bytes > self.policy.max_size_bytes:
            raise UploadValidationError("Uploaded file exceeds maximum size")
        if extension not in self.policy.allowed_extensions:
            raise UploadValidationError("Uploaded file extension is not allowed")
        if guessed_mime not in self.policy.allowed_mime_types:
            raise UploadValidationError("Uploaded file MIME type is not allowed")
        if self.policy.require_probe and inspection.size_bytes == 0:
            raise UploadValidationError("Uploaded media probe failed")
        return UploadValidationResult(path=inspection.path, sha256=inspection.sha256, size_bytes=inspection.size_bytes, mime_type=guessed_mime, extension=extension)
