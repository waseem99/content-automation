from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from urllib.parse import quote

from src.application.assets.hashing import inspect_file
from src.application.shared_storage.models import SharedObjectResult


class SharedStorageError(RuntimeError):
    pass


class SharedObjectMissing(SharedStorageError):
    pass


class SharedObjectHashMismatch(SharedStorageError):
    pass


@dataclass(frozen=True, slots=True)
class SharedAccessTarget:
    kind: str
    value: str | Path
    mime_type: str | None
    filename: str | None


class SharedStorageProvider(Protocol):
    backend_key: str

    def put_file(
        self,
        source: Path,
        *,
        object_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
        mime_type: str | None,
        metadata: dict[str, Any],
    ) -> SharedObjectResult: ...

    def verify(
        self,
        *,
        object_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> SharedObjectResult: ...

    def access_target(
        self,
        *,
        object_key: str,
        expires_in_seconds: int,
        mime_type: str | None,
        filename: str | None,
    ) -> SharedAccessTarget: ...

    def delete(self, *, object_key: str) -> None: ...


class LocalSharedStorageProvider:
    def __init__(self, *, backend_key: str, root: Path) -> None:
        self.backend_key = backend_key
        self.root = root.expanduser().resolve()

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise SharedStorageError(f"Shared local storage root is unavailable: {self.root}")

    def put_file(
        self,
        source: Path,
        *,
        object_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
        mime_type: str | None,
        metadata: dict[str, Any],
    ) -> SharedObjectResult:
        self.ensure_ready()
        source = source.expanduser().resolve(strict=True)
        inspected = inspect_file(source)
        self._require_expected(inspected.sha256, inspected.size_bytes, expected_sha256, expected_size_bytes)
        target = self._path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = inspect_file(target)
            self._require_expected(existing.sha256, existing.size_bytes, expected_sha256, expected_size_bytes)
        else:
            descriptor, temporary_name = tempfile.mkstemp(prefix=".shared-", dir=target.parent)
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_file:
                    shutil.copyfileobj(input_file, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                copied = inspect_file(temporary)
                self._require_expected(copied.sha256, copied.size_bytes, expected_sha256, expected_size_bytes)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        return SharedObjectResult(
            object_key=self._normalize_key(object_key),
            storage_uri=f"shared+local:///{quote(self.backend_key)}/{quote(self._normalize_key(object_key), safe='/')}",
            sha256=expected_sha256,
            size_bytes=expected_size_bytes,
            mime_type=mime_type,
            local_path=target,
            metadata=dict(metadata),
        )

    def verify(
        self,
        *,
        object_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> SharedObjectResult:
        path = self._path(object_key)
        if not path.is_file():
            raise SharedObjectMissing(f"Shared object is missing: {object_key}")
        inspected = inspect_file(path)
        self._require_expected(inspected.sha256, inspected.size_bytes, expected_sha256, expected_size_bytes)
        return SharedObjectResult(
            object_key=self._normalize_key(object_key),
            storage_uri=f"shared+local:///{quote(self.backend_key)}/{quote(self._normalize_key(object_key), safe='/')}",
            sha256=inspected.sha256,
            size_bytes=inspected.size_bytes,
            mime_type=inspected.mime_type,
            local_path=path,
        )

    def access_target(
        self,
        *,
        object_key: str,
        expires_in_seconds: int,
        mime_type: str | None,
        filename: str | None,
    ) -> SharedAccessTarget:
        del expires_in_seconds
        path = self._path(object_key)
        if not path.is_file():
            raise SharedObjectMissing(f"Shared object is missing: {object_key}")
        return SharedAccessTarget(kind="file", value=path, mime_type=mime_type, filename=filename)

    def delete(self, *, object_key: str) -> None:
        path = self._path(object_key)
        if path.exists() and not path.is_file():
            raise SharedStorageError(f"Shared object path is not a file: {object_key}")
        path.unlink(missing_ok=True)

    def _path(self, object_key: str) -> Path:
        normalized = self._normalize_key(object_key)
        target = (self.root / normalized).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise SharedStorageError(f"Object key escapes storage root: {object_key}") from exc
        return target

    @staticmethod
    def _normalize_key(object_key: str) -> str:
        candidate = PurePosixPath(object_key)
        if candidate.is_absolute() or not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
            raise SharedStorageError(f"Invalid shared object key: {object_key}")
        normalized = candidate.as_posix()
        if "\\" in object_key:
            raise SharedStorageError(f"Invalid shared object key: {object_key}")
        return normalized

    @staticmethod
    def _require_expected(
        observed_sha256: str,
        observed_size: int,
        expected_sha256: str,
        expected_size: int,
    ) -> None:
        if observed_sha256 != expected_sha256 or observed_size != expected_size:
            raise SharedObjectHashMismatch(
                f"Shared object checksum mismatch: expected {expected_sha256}/{expected_size}, "
                f"observed {observed_sha256}/{observed_size}"
            )


class S3CompatibleClient(Protocol):
    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs: dict[str, Any] | None = None) -> Any: ...

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]: ...

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict[str, Any],
        ExpiresIn: int,
    ) -> str: ...

    def delete_object(self, *, Bucket: str, Key: str) -> Any: ...


class S3CompatibleSharedStorageProvider:
    def __init__(
        self,
        *,
        backend_key: str,
        bucket: str,
        client: S3CompatibleClient,
        base_prefix: str = "",
    ) -> None:
        self.backend_key = backend_key
        self.bucket = bucket
        self.client = client
        self.base_prefix = base_prefix.strip("/")

    def put_file(
        self,
        source: Path,
        *,
        object_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
        mime_type: str | None,
        metadata: dict[str, Any],
    ) -> SharedObjectResult:
        source = source.expanduser().resolve(strict=True)
        inspection = inspect_file(source)
        if inspection.sha256 != expected_sha256 or inspection.size_bytes != expected_size_bytes:
            raise SharedObjectHashMismatch("Source bytes do not match the canonical asset")
        key = self._key(object_key)
        extra = {
            "Metadata": {
                "sha256": expected_sha256,
                "size-bytes": str(expected_size_bytes),
                **{str(k): str(v) for k, v in metadata.items() if isinstance(v, (str, int, float, bool))},
            }
        }
        if mime_type:
            extra["ContentType"] = mime_type
        self.client.upload_file(str(source), self.bucket, key, ExtraArgs=extra)
        return self.verify(
            object_key=object_key,
            expected_sha256=expected_sha256,
            expected_size_bytes=expected_size_bytes,
        ).model_copy(update={"mime_type": mime_type, "metadata": dict(metadata)})

    def verify(
        self,
        *,
        object_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> SharedObjectResult:
        key = self._key(object_key)
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise SharedObjectMissing(f"S3-compatible object is missing: {key}") from exc
        metadata = {str(k).lower(): str(v) for k, v in dict(head.get("Metadata") or {}).items()}
        observed_sha = metadata.get("sha256")
        observed_size = int(head.get("ContentLength", metadata.get("size-bytes", -1)))
        if observed_sha != expected_sha256 or observed_size != expected_size_bytes:
            raise SharedObjectHashMismatch(
                f"S3-compatible object checksum metadata mismatch for {key}"
            )
        version = head.get("VersionId")
        etag = str(head.get("ETag", "")).strip('"') or None
        return SharedObjectResult(
            object_key=key,
            storage_uri=f"shared+s3://{quote(self.bucket)}/{quote(key, safe='/')}",
            object_version=str(version) if version else None,
            etag=etag,
            sha256=expected_sha256,
            size_bytes=expected_size_bytes,
            mime_type=head.get("ContentType"),
            metadata=metadata,
        )

    def access_target(
        self,
        *,
        object_key: str,
        expires_in_seconds: int,
        mime_type: str | None,
        filename: str | None,
    ) -> SharedAccessTarget:
        key = self._key(object_key)
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'inline; filename="{filename.replace(chr(34), "")}"'
        if mime_type:
            params["ResponseContentType"] = mime_type
        url = self.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in_seconds,
        )
        return SharedAccessTarget(kind="redirect", value=url, mime_type=mime_type, filename=filename)

    def delete(self, *, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(object_key))

    def _key(self, object_key: str) -> str:
        normalized = LocalSharedStorageProvider._normalize_key(object_key)
        return f"{self.base_prefix}/{normalized}" if self.base_prefix else normalized


def content_addressed_key(*, sha256: str, filename: str | None = None) -> str:
    safe_name = "object"
    if filename:
        candidate = Path(filename).name
        safe_name = "".join(character if character.isalnum() or character in "._-" else "_" for character in candidate)
        safe_name = safe_name or "object"
    return f"assets/{sha256[:2]}/{sha256}/{safe_name}"


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
