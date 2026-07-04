from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from src.application.assets.exceptions import FileChangedDuringHashing, InvalidAssetPath
from src.application.assets.models import FileInspection


DEFAULT_CHUNK_SIZE = 1024 * 1024


def inspect_file(path: Path, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> FileInspection:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise InvalidAssetPath(f"Asset path is not a regular file: {resolved}")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    before = resolved.stat()
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    after = resolved.stat()

    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise FileChangedDuringHashing(f"File changed while hashing: {resolved}")

    mime_type, _ = mimetypes.guess_type(resolved.name)
    return FileInspection(
        path=resolved,
        sha256=digest.hexdigest(),
        size_bytes=after.st_size,
        mime_type=mime_type,
        original_filename=resolved.name,
        mtime_ns=after.st_mtime_ns,
    )
