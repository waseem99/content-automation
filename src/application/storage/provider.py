from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from src.application.assets.hashing import inspect_file
from src.application.storage.models import AccessLevel, SignedUrlRequest, SignedUrlResult, StorageObject, StoragePurpose, expires_after


class StorageError(RuntimeError):
    pass


class StoragePathError(StorageError):
    pass


class LocalStorageProvider:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def purpose_root(self, purpose: StoragePurpose) -> Path:
        return self.root / purpose.value

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise StorageError(f"Storage root is unavailable: {self.root}")
        for purpose in StoragePurpose:
            self.purpose_root(purpose).mkdir(parents=True, exist_ok=True)

    def put_file(self, source: Path, *, purpose: StoragePurpose, name: str | None = None, metadata: dict | None = None) -> StorageObject:
        self.ensure_ready()
        source = source.expanduser().resolve(strict=True)
        if not source.is_file():
            raise StoragePathError(f"Source file is missing: {source}")
        safe_name = self._safe_name(name or source.name)
        target = (self.purpose_root(purpose) / safe_name).resolve()
        self._ensure_within(target, self.purpose_root(purpose))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        inspection = inspect_file(target)
        return StorageObject(
            uri=self.uri_for(purpose, target),
            purpose=purpose,
            path=target,
            size_bytes=inspection.size_bytes,
            sha256=inspection.sha256,
            metadata=metadata or {},
        )

    def resolve(self, uri: str) -> Path:
        if not uri.startswith("local:///"):
            raise StoragePathError(f"Unsupported local storage URI: {uri}")
        relative = uri.removeprefix("local:///")
        target = (self.root / relative).resolve()
        self._ensure_within(target, self.root)
        return target

    def signed_url(self, request: SignedUrlRequest) -> SignedUrlResult:
        path = self.resolve(request.uri)
        if not path.exists():
            raise StoragePathError(f"Cannot sign missing object: {request.uri}")
        expires_at = expires_after(request.expires_in_seconds)
        return SignedUrlResult(
            url=f"dev-signed://{quote(request.uri, safe='')}?expires={int(expires_at.timestamp())}&access={request.access_level.value}",
            expires_at=expires_at,
            access_level=request.access_level,
            purpose=request.purpose,
        )

    def uri_for(self, purpose: StoragePurpose, path: Path) -> str:
        resolved = path.expanduser().resolve(strict=True)
        self._ensure_within(resolved, self.purpose_root(purpose))
        relative = resolved.relative_to(self.root).as_posix()
        return f"local:///{relative}"

    def access_level_for(self, purpose: StoragePurpose) -> AccessLevel:
        if purpose == StoragePurpose.RIGHTS_EVIDENCE:
            return AccessLevel.RESTRICTED
        if purpose == StoragePurpose.TEMP:
            return AccessLevel.TEMPORARY
        return AccessLevel.INTERNAL

    @staticmethod
    def _safe_name(name: str) -> str:
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            raise StoragePathError("Invalid storage object name")
        return name

    @staticmethod
    def _ensure_within(target: Path, root: Path) -> None:
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise StoragePathError(f"Path escapes storage root: {target}") from exc
