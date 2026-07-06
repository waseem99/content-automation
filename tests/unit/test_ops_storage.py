from datetime import datetime, timedelta, timezone

import pytest

from src.application.storage.models import AccessLevel, SignedUrlRequest, StoragePurpose
from src.application.storage.provider import LocalStorageProvider, StoragePathError
from src.application.storage.temp import TemporaryFileManager


def test_local_storage_rejects_path_traversal_name(tmp_path):
    storage = LocalStorageProvider(tmp_path / "storage")
    source = tmp_path / "file.txt"
    source.write_text("hello")
    with pytest.raises(StoragePathError):
        storage.put_file(source, purpose=StoragePurpose.ASSET, name="../bad.txt")


def test_rights_evidence_uses_restricted_access(tmp_path):
    storage = LocalStorageProvider(tmp_path / "storage")
    assert storage.access_level_for(StoragePurpose.RIGHTS_EVIDENCE) == AccessLevel.RESTRICTED


def test_signed_url_has_expiry_and_access(tmp_path):
    storage = LocalStorageProvider(tmp_path / "storage")
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"pdf")
    obj = storage.put_file(source, purpose=StoragePurpose.RIGHTS_EVIDENCE)
    signed = storage.signed_url(SignedUrlRequest(uri=obj.uri, purpose=obj.purpose, access_level=AccessLevel.RESTRICTED, expires_in_seconds=60))
    assert signed.url.startswith("dev-signed://")
    assert "access=restricted" in signed.url
    assert signed.expires_at > datetime.now(timezone.utc)


def test_temp_cleanup_deletes_only_expired_temp_files(tmp_path):
    storage = LocalStorageProvider(tmp_path / "storage")
    temp_file = tmp_path / "temp.txt"
    asset_file = tmp_path / "asset.txt"
    temp_file.write_text("temp")
    asset_file.write_text("asset")
    manager = TemporaryFileManager(storage, retention_seconds=1)
    temp_record = manager.register(temp_file)
    asset = storage.put_file(asset_file, purpose=StoragePurpose.ASSET)
    old_time = datetime.now(timezone.utc).timestamp() - 10
    temp_record.path.touch()
    import os
    os.utime(temp_record.path, (old_time, old_time))
    summary = manager.cleanup_expired(now=datetime.now(timezone.utc), registered_uris={asset.uri})
    assert summary.deleted == 1
    assert not temp_record.path.exists()
    assert asset.path.exists()
