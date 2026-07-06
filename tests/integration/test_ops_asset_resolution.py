from __future__ import annotations

import pytest

from src.application.assets.resolver import AssetResolver
from src.application.assets.storage import StorageUriResolver
from src.application.assets.hashing import inspect_file
from src.domain.asset_enums import AssetType
from src.domain.asset_models import AssetCreate
from src.domain.asset_status import AssetLifecycleStatus, AssetSourceType
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import close_database, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_registered_asset_resolves_by_asset_id(database, tmp_path):
    workspace = tmp_path / "workspace"
    managed = tmp_path / "managed"
    workspace.mkdir()
    managed.mkdir()
    media = workspace / "image.png"
    media.write_bytes(b"asset-bytes")
    resolver = StorageUriResolver(workspace_root=workspace, managed_root=managed)
    inspection = inspect_file(media)
    with unit_of_work(database) as uow:
        asset = uow.assets.create(
            AssetCreate(
                asset_type=AssetType.IMAGE,
                source_type=AssetSourceType.OWNED,
                lifecycle_status=AssetLifecycleStatus.APPROVED,
                storage_uri=resolver.workspace_uri(media),
                sha256=inspection.sha256,
                original_filename=media.name,
                mime_type=inspection.mime_type,
                size_bytes=inspection.size_bytes,
                created_by="pytest",
            )
        )
    resolved = AssetResolver(database, resolver).resolve(asset.id)
    assert resolved.path == media.resolve()
    assert resolved.asset.sha256 == inspection.sha256
