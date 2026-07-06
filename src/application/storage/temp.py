from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.application.storage.models import CleanupSummary, TempFileRecord, StoragePurpose
from src.application.storage.provider import LocalStorageProvider, StoragePathError


class TemporaryFileManager:
    def __init__(self, storage: LocalStorageProvider, *, retention_seconds: int = 86_400) -> None:
        if retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")
        self.storage = storage
        self.retention_seconds = retention_seconds

    def register(self, path: Path, *, metadata: dict | None = None) -> TempFileRecord:
        obj = self.storage.put_file(path, purpose=StoragePurpose.TEMP, metadata=metadata)
        return TempFileRecord(
            path=obj.path,
            uri=obj.uri,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.retention_seconds),
            metadata=obj.metadata,
        )

    def cleanup_expired(self, *, now: datetime | None = None, registered_uris: set[str] | None = None) -> CleanupSummary:
        now = now or datetime.now(timezone.utc)
        registered_uris = registered_uris or set()
        temp_root = self.storage.purpose_root(StoragePurpose.TEMP)
        temp_root.mkdir(parents=True, exist_ok=True)
        scanned = deleted = skipped = 0
        deleted_paths: list[str] = []
        cutoff = now.timestamp() - self.retention_seconds
        for path in temp_root.rglob("*"):
            if not path.is_file():
                continue
            scanned += 1
            try:
                uri = self.storage.uri_for(StoragePurpose.TEMP, path)
            except StoragePathError:
                skipped += 1
                continue
            if uri in registered_uris:
                skipped += 1
                continue
            if path.stat().st_mtime <= cutoff:
                path.unlink()
                deleted += 1
                deleted_paths.append(str(path))
            else:
                skipped += 1
        return CleanupSummary(scanned=scanned, deleted=deleted, skipped=skipped, deleted_paths=tuple(deleted_paths))
