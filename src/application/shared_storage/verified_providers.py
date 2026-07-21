from __future__ import annotations

import tempfile
from pathlib import Path

from src.application.assets.hashing import inspect_file
from src.application.shared_storage.models import SharedObjectResult
from src.application.shared_storage.providers import (
    S3CompatibleSharedStorageProvider,
    SharedObjectHashMismatch,
)


class VerifiedS3CompatibleSharedStorageProvider(S3CompatibleSharedStorageProvider):
    """S3-compatible provider whose verification hashes downloaded bytes."""

    def verify(
        self,
        *,
        object_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> SharedObjectResult:
        metadata_result = super().verify(
            object_key=object_key,
            expected_sha256=expected_sha256,
            expected_size_bytes=expected_size_bytes,
        )
        download_file = getattr(self.client, "download_file", None)
        if download_file is None:
            raise SharedObjectHashMismatch(
                "S3-compatible byte verification requires a client download_file implementation"
            )
        descriptor, temporary_name = tempfile.mkstemp(prefix="shared-restore-")
        Path(temporary_name).unlink(missing_ok=True)
        try:
            import os

            os.close(descriptor)
            download_file(self.bucket, self._key(object_key), temporary_name)
            inspected = inspect_file(Path(temporary_name))
            if inspected.sha256 != expected_sha256 or inspected.size_bytes != expected_size_bytes:
                raise SharedObjectHashMismatch(
                    f"Restored S3-compatible object bytes do not match {object_key}"
                )
            return metadata_result
        finally:
            Path(temporary_name).unlink(missing_ok=True)
