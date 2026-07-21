from __future__ import annotations

from pathlib import Path

import pytest

from src.application.assets.hashing import inspect_file
from src.application.shared_storage.providers import (
    LocalSharedStorageProvider,
    SharedObjectHashMismatch,
    content_addressed_key,
)
from src.application.shared_storage.verified_providers import (
    VerifiedS3CompatibleSharedStorageProvider,
)


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.metadata: dict[tuple[str, str], dict] = {}

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        data = Path(filename).read_bytes()
        self.objects[(bucket, key)] = data
        extra = dict(ExtraArgs or {})
        self.metadata[(bucket, key)] = {
            "ContentLength": len(data),
            "ContentType": extra.get("ContentType"),
            "Metadata": dict(extra.get("Metadata") or {}),
            "ETag": '"fake-etag"',
            "VersionId": "version-1",
        }

    def head_object(self, *, Bucket, Key):
        return dict(self.metadata[(Bucket, Key)])

    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
        return f"https://objects.example.test/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"

    def delete_object(self, *, Bucket, Key):
        self.objects.pop((Bucket, Key), None)
        self.metadata.pop((Bucket, Key), None)

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[(bucket, key)])


def test_local_provider_is_content_addressed_and_rejects_corruption(tmp_path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"P95 local content-addressed bytes")
    inspected = inspect_file(source)
    provider = LocalSharedStorageProvider(backend_key="local-test", root=tmp_path / "objects")
    key = content_addressed_key(sha256=inspected.sha256, filename=source.name)
    stored = provider.put_file(
        source,
        object_key=key,
        expected_sha256=inspected.sha256,
        expected_size_bytes=inspected.size_bytes,
        mime_type="application/octet-stream",
        metadata={"test": True},
    )
    assert stored.local_path.read_bytes() == source.read_bytes()
    assert provider.verify(
        object_key=key,
        expected_sha256=inspected.sha256,
        expected_size_bytes=inspected.size_bytes,
    ).sha256 == inspected.sha256
    stored.local_path.write_bytes(b"corrupted")
    with pytest.raises(SharedObjectHashMismatch):
        provider.verify(
            object_key=key,
            expected_sha256=inspected.sha256,
            expected_size_bytes=inspected.size_bytes,
        )


def test_s3_compatible_provider_hashes_downloaded_bytes_and_presigns(tmp_path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"P95 S3-compatible bytes" * 20)
    inspected = inspect_file(source)
    client = FakeS3Client()
    provider = VerifiedS3CompatibleSharedStorageProvider(
        backend_key="s3-test",
        bucket="p95-bucket",
        client=client,
        base_prefix="shared",
    )
    key = content_addressed_key(sha256=inspected.sha256, filename=source.name)
    stored = provider.put_file(
        source,
        object_key=key,
        expected_sha256=inspected.sha256,
        expected_size_bytes=inspected.size_bytes,
        mime_type="video/mp4",
        metadata={"phase": "P95"},
    )
    assert stored.object_version == "version-1"
    assert stored.etag == "fake-etag"
    assert provider.verify(
        object_key=key,
        expected_sha256=inspected.sha256,
        expected_size_bytes=inspected.size_bytes,
    ).sha256 == inspected.sha256
    target = provider.access_target(
        object_key=key,
        expires_in_seconds=300,
        mime_type="video/mp4",
        filename="review.mp4",
    )
    assert target.kind == "redirect"
    assert "expires=300" in str(target.value)

    client.objects[("p95-bucket", f"shared/{key}")] = b"corrupted but metadata unchanged"
    with pytest.raises(SharedObjectHashMismatch):
        provider.verify(
            object_key=key,
            expected_sha256=inspected.sha256,
            expected_size_bytes=inspected.size_bytes,
        )
