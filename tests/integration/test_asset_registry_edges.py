from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from src.application.assets.backfill import BackfillService
from src.application.assets.classification import AssetClassificationPolicy, AssetContext
from src.application.assets.exceptions import FileChangedDuringHashing
from src.application.assets.models import RegisterFileRequest, StorageMode
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


def test_stale_inspection_is_rejected_without_database_write(runtime, tmp_path: Path) -> None:
    database, registry = runtime
    path = tmp_path / "data" / "source.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"original")
    classification = AssetClassificationPolicy().classify(AssetContext.SOURCE_MATCH_VIDEO)
    request = RegisterFileRequest(
        path=path,
        asset_type=classification.asset_type,
        source_type=classification.source_type,
        lifecycle_status=classification.lifecycle_status,
        storage_mode=StorageMode.REFERENCE_IN_PLACE,
    )
    inspection = registry.inspect(request)
    path.write_bytes(b"changed-after-inspection")

    with pytest.raises(FileChangedDuringHashing):
        with unit_of_work(database) as uow:
            registry.register_inspection_in_uow(uow, request, inspection)

    with database.transaction() as conn:
        count = conn.execute(
            "SELECT count(*) AS total FROM football_brief.assets"
        ).fetchone()["total"]
    assert count == 0


def test_manifest_source_outside_input_folder_is_internal_only(runtime, tmp_path: Path) -> None:
    database, registry = runtime
    data_root = tmp_path / "data"
    source = data_root / "footage" / "source.mp4"
    run_dir = data_root / "runs" / "one"
    clip = run_dir / "clip_01.mp4"
    source.parent.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    source.write_bytes(b"source-footage")
    clip.write_bytes(b"derived-clip")
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "source_video": str(source.resolve()),
                "clips": [{"file": clip.name}],
            }
        ),
        encoding="utf-8",
    )

    report = BackfillService(database, registry).run(root=data_root, commit=True)

    source_entry = next(entry for entry in report.entries if entry.path == "footage/source.mp4")
    clip_entry = next(entry for entry in report.entries if entry.path.endswith("clip_01.mp4"))
    assert source_entry.lifecycle_status == "internal_only"
    assert source_entry.source_type == "client_supplied"
    assert clip_entry.lifecycle_status == "internal_only"
    assert clip_entry.parent_asset_id == source_entry.asset_id
