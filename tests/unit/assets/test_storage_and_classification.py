from __future__ import annotations

import pytest

from src.application.assets.classification import AssetClassificationPolicy, AssetContext
from src.application.assets.exceptions import InvalidAssetPath, UnsupportedStorageUri
from src.application.assets.storage import StorageUriResolver
from src.domain.asset_status import AssetLifecycleStatus


def test_workspace_uri_round_trip(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    managed = workspace / "data" / "asset_store"
    file_path = workspace / "data" / "input" / "match.mp4"
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"video")
    resolver = StorageUriResolver(workspace, managed)

    uri = resolver.workspace_uri(file_path)

    assert uri.startswith("workspace:///")
    assert resolver.to_path(uri) == file_path.resolve()


def test_workspace_uri_rejects_external_file(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    external = tmp_path / "external.mp4"
    external.write_bytes(b"video")
    resolver = StorageUriResolver(workspace, workspace / "store")

    with pytest.raises(InvalidAssetPath):
        resolver.workspace_uri(external)


def test_unknown_uri_scheme_is_rejected(tmp_path) -> None:
    resolver = StorageUriResolver(tmp_path, tmp_path / "store")
    with pytest.raises(UnsupportedStorageUri):
        resolver.to_path("https://example.com/file.mp4")


def test_match_clips_and_web_images_fail_closed() -> None:
    policy = AssetClassificationPolicy()

    clip = policy.classify(AssetContext.EXTRACTED_MATCH_CLIP)
    web = policy.classify(AssetContext.WEB_IMAGE_SOURCE)

    assert clip.lifecycle_status == AssetLifecycleStatus.INTERNAL_ONLY
    assert web.lifecycle_status == AssetLifecycleStatus.CANDIDATE
