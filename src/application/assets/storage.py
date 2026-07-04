from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from src.application.assets.exceptions import (
    AssetHashMismatch,
    AssetStorageMissing,
    InvalidAssetPath,
    UnsupportedStorageUri,
)
from src.application.assets.hashing import inspect_file
from src.application.assets.models import FileInspection


@dataclass(frozen=True, slots=True)
class StorageUriResolver:
    workspace_root: Path
    managed_root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_root", self.workspace_root.expanduser().resolve())
        object.__setattr__(self, "managed_root", self.managed_root.expanduser().resolve())

    def workspace_uri(self, path: Path) -> str:
        resolved = path.expanduser().resolve(strict=True)
        try:
            relative = resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise InvalidAssetPath(
                f"Referenced asset must be inside workspace root {self.workspace_root}: {resolved}"
            ) from exc
        return f"workspace:///{quote(relative.as_posix())}"

    def managed_uri(self, sha256: str) -> str:
        if len(sha256) != 64:
            raise ValueError("Managed asset SHA-256 must contain 64 hexadecimal characters")
        return f"managed:///{sha256[:2]}/{sha256}"

    def managed_path(self, sha256: str) -> Path:
        return self.managed_root / sha256[:2] / sha256

    def to_path(self, uri: str) -> Path:
        parsed = urlsplit(uri)
        relative = unquote(parsed.path.lstrip("/"))
        if parsed.scheme == "workspace":
            target = (self.workspace_root / relative).resolve()
            self._ensure_within(target, self.workspace_root)
            return target
        if parsed.scheme == "managed":
            target = (self.managed_root / relative).resolve()
            self._ensure_within(target, self.managed_root)
            return target
        raise UnsupportedStorageUri(f"Unsupported asset storage URI: {uri}")

    @staticmethod
    def _ensure_within(target: Path, root: Path) -> None:
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise UnsupportedStorageUri(f"Storage URI escapes configured root: {target}") from exc


class ManagedAssetStore:
    def __init__(self, resolver: StorageUriResolver) -> None:
        self.resolver = resolver

    def copy(self, inspection: FileInspection) -> tuple[Path, str]:
        destination = self.resolver.managed_path(inspection.sha256)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing = inspect_file(destination)
            if existing.sha256 != inspection.sha256:
                raise AssetHashMismatch(f"Managed asset hash mismatch: {destination}")
            return destination, self.resolver.managed_uri(inspection.sha256)

        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{inspection.sha256}.",
            dir=destination.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as target, inspection.path.open("rb") as source:
                shutil.copyfileobj(source, target, length=1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            copied = inspect_file(temporary)
            if copied.sha256 != inspection.sha256:
                raise AssetHashMismatch(
                    f"Managed copy does not match inspected source: {inspection.path}"
                )
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination, self.resolver.managed_uri(inspection.sha256)

    def require(self, uri: str) -> Path:
        path = self.resolver.to_path(uri)
        if not path.is_file():
            raise AssetStorageMissing(f"Registered asset bytes are missing: {path}")
        return path
