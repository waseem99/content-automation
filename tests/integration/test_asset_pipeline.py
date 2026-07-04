from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from src.application.assets.pipeline import (
    register_extraction_manifest,
    register_web_image_pair,
)
from src.application.assets.registry import AssetRegistryService
from src.application.assets.storage import ManagedAssetStore, StorageUriResolver
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings
from src.infrastructure.database.uow import unit_of_work


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.integration


@pytest.fixture()
def runtime(tmp_path: Path):
    if not TEST_DSN:
        pytest.skip("FOOTBALL_BRIEF_TEST_DATABASE_URL is not configured")
    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr(TEST_DSN),
        migrations_dir=ROOT / "migrations",
        require_schema=False,
        pool_min_size=1,
        pool_max_size=4,
    )
    database = Database(settings)
    database.open(require_schema=False)
    with database.transaction() as conn:
        conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
    apply_migrations(database, settings.migrations_dir)
    resolver = StorageUriResolver(tmp_path, tmp_path / "data" / "asset_store")
    registry = AssetRegistryService(database, resolver, ManagedAssetStore(resolver))
    try:
        yield database, registry
    finally:
        with database.transaction() as conn:
            conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
        database.close()


def test_extraction_manifest_receives_canonical_asset_ids(runtime, tmp_path: Path) -> None:
    database, registry = runtime
    source = tmp_path / "data" / "input" / "match.mp4"
    run_dir = tmp_path / "data" / "output" / "run"
    clip = run_dir / "clip_01.mp4"
    source.parent.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    source.write_bytes(b"source-match")
    clip.write_bytes(b"clip-one")
    manifest = run_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source_video": str(source),
                "clips": [{"file": clip.name}],
            }
        ),
        encoding="utf-8",
    )

    updated = register_extraction_manifest(
        manifest_path=manifest,
        source_video=source,
        clip_paths=[clip],
        registry=registry,
        created_by="pytest",
    )

    source_id = updated["source_asset_id"]
    clip_entry = updated["clips"][0]
    assert updated["registry_status"] == "registered"
    assert clip_entry["parent_asset_id"] == source_id
    with unit_of_work(database) as uow:
        source_asset = uow.assets.get(source_id)
        clip_asset = uow.assets.get(clip_entry["asset_id"])
    assert source_asset.lifecycle_status.value == "internal_only"
    assert clip_asset.lifecycle_status.value == "internal_only"
    assert str(clip_asset.parent_asset_id) == source_id


def test_web_image_pair_preserves_original_and_derivative(runtime, tmp_path: Path) -> None:
    database, registry = runtime
    original = tmp_path / "data" / "images" / "player_source.jpg"
    normalized = tmp_path / "data" / "images" / "player.png"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"original-downloaded-bytes")
    normalized.write_bytes(b"normalized-png-bytes")

    source_handle, derivative_handle = register_web_image_pair(
        original_path=original,
        normalized_path=normalized,
        registry=registry,
        metadata={"source_url": "https://example.invalid/player.jpg"},
        created_by="pytest",
    )

    with unit_of_work(database) as uow:
        source_asset = uow.assets.get(source_handle.asset_id)
        derivative_asset = uow.assets.get(derivative_handle.asset_id)
    assert source_asset.lifecycle_status.value == "candidate"
    assert source_asset.storage_uri.startswith("managed:///")
    assert derivative_asset.lifecycle_status.value == "candidate"
    assert derivative_asset.parent_asset_id == source_asset.id
