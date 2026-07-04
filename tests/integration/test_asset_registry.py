from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import pytest
from psycopg.errors import ForeignKeyViolation
from pydantic import SecretStr

from src.application.assets.backfill import BackfillService
from src.application.assets.classification import AssetClassificationPolicy, AssetContext
from src.application.assets.evidence import RightsEvidenceService
from src.application.assets.exceptions import AssetHashMismatch
from src.application.assets.models import RegisterFileRequest, StorageMode
from src.application.assets.registry import AssetRegistryService
from src.application.assets.resolver import AssetResolver
from src.application.assets.storage import ManagedAssetStore, StorageUriResolver
from src.domain.evidence_models import RightsEvidenceType
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings
from src.infrastructure.database.uow import unit_of_work


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.integration


@pytest.fixture()
def database() -> Database:
    if not TEST_DSN:
        pytest.skip("FOOTBALL_BRIEF_TEST_DATABASE_URL is not configured")
    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr(TEST_DSN),
        migrations_dir=ROOT / "migrations",
        require_schema=False,
        pool_min_size=1,
        pool_max_size=8,
    )
    db = Database(settings)
    db.open(require_schema=False)
    with db.transaction() as conn:
        conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
    apply_migrations(db, settings.migrations_dir)
    try:
        yield db
    finally:
        with db.transaction() as conn:
            conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
        db.close()


@pytest.fixture()
def registry(database: Database, tmp_path: Path) -> AssetRegistryService:
    resolver = StorageUriResolver(tmp_path, tmp_path / "data" / "asset_store")
    return AssetRegistryService(database, resolver, ManagedAssetStore(resolver))


def _request(
    path: Path,
    context: AssetContext,
    *,
    parent_asset_id: UUID | None = None,
    managed: bool = False,
) -> RegisterFileRequest:
    classification = AssetClassificationPolicy().classify(context, path)
    return RegisterFileRequest(
        path=path,
        asset_type=classification.asset_type,
        source_type=classification.source_type,
        lifecycle_status=classification.lifecycle_status,
        storage_mode=(
            StorageMode.COPY_TO_MANAGED_STORE
            if managed
            else StorageMode.REFERENCE_IN_PLACE
        ),
        parent_asset_id=parent_asset_id,
        created_by="pytest",
    )


def _asset_count(database: Database) -> int:
    with database.transaction() as conn:
        return int(conn.execute("SELECT count(*) AS total FROM football_brief.assets").fetchone()["total"])


def test_identical_bytes_reuse_one_canonical_asset(
    database: Database,
    registry: AssetRegistryService,
    tmp_path: Path,
) -> None:
    first = tmp_path / "data" / "first.mp4"
    second = tmp_path / "data" / "second.mp4"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"identical-video-bytes")
    second.write_bytes(b"identical-video-bytes")

    first_result = registry.register_file(_request(first, AssetContext.SOURCE_MATCH_VIDEO))
    second_result = registry.register_file(_request(second, AssetContext.SOURCE_MATCH_VIDEO))

    assert first_result.created is True
    assert second_result.created is False
    assert first_result.asset.id == second_result.asset.id
    assert _asset_count(database) == 1


def test_concurrent_duplicate_registration_creates_one_asset(
    database: Database,
    registry: AssetRegistryService,
    tmp_path: Path,
) -> None:
    path = tmp_path / "data" / "concurrent.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"one canonical result under concurrency")
    request = _request(path, AssetContext.SOURCE_MATCH_VIDEO)

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: registry.register_file(request), range(12)))

    assert len({result.asset.id for result in results}) == 1
    assert sum(result.created for result in results) == 1
    assert _asset_count(database) == 1


def test_derivative_keeps_parent_and_parent_delete_is_restricted(
    database: Database,
    registry: AssetRegistryService,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "data" / "image_source.jpg"
    derivative_path = tmp_path / "data" / "image.png"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"source-image")
    derivative_path.write_bytes(b"normalized-image")

    source = registry.register_file(_request(source_path, AssetContext.WEB_IMAGE_SOURCE))
    derivative = registry.register_file(
        _request(
            derivative_path,
            AssetContext.WEB_IMAGE_DERIVATIVE,
            parent_asset_id=source.asset.id,
        )
    )

    assert derivative.asset.parent_asset_id == source.asset.id
    with pytest.raises(ForeignKeyViolation):
        with database.transaction() as conn:
            conn.execute(
                "DELETE FROM football_brief.assets WHERE id = %s",
                (source.asset.id,),
            )


def test_evidence_is_canonical_atomic_and_restricts_target_delete(
    database: Database,
    registry: AssetRegistryService,
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "data" / "licensed-image.png"
    evidence_path = tmp_path / "evidence" / "license.pdf"
    target_path.parent.mkdir(parents=True)
    evidence_path.parent.mkdir(parents=True)
    target_path.write_bytes(b"licensed-image")
    evidence_path.write_bytes(b"signed-license-document")
    target = registry.register_file(_request(target_path, AssetContext.WEB_IMAGE_SOURCE))

    evidence = RightsEvidenceService(database, registry).register(
        target_asset_id=target.asset.id,
        evidence_path=evidence_path,
        evidence_type=RightsEvidenceType.LICENSE,
        uploaded_by="pytest",
    )

    with unit_of_work(database) as uow:
        evidence_asset = uow.assets.get(evidence.evidence_asset_id)
    assert evidence_asset.asset_type.value == "license_evidence"
    assert evidence_asset.storage_uri.startswith("managed:///")
    assert evidence.sha256 == evidence_asset.sha256
    with pytest.raises(ForeignKeyViolation):
        with database.transaction() as conn:
            conn.execute(
                "DELETE FROM football_brief.assets WHERE id = %s",
                (target.asset.id,),
            )


def test_resolver_rejects_tampered_bytes(
    database: Database,
    registry: AssetRegistryService,
    tmp_path: Path,
) -> None:
    path = tmp_path / "data" / "tamper.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"original")
    result = registry.register_file(_request(path, AssetContext.SOURCE_MATCH_VIDEO))
    path.write_bytes(b"tampered")

    resolver = AssetResolver(database, registry.storage_resolver)
    with pytest.raises(AssetHashMismatch):
        resolver.resolve(result.asset.id)


def test_backfill_is_dry_run_safe_and_idempotent(
    database: Database,
    registry: AssetRegistryService,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    source = data_root / "input" / "match.mp4"
    run_dir = data_root / "output" / "run-001"
    clip = run_dir / "clip_01.mp4"
    source.parent.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    source.write_bytes(b"match-source")
    clip.write_bytes(b"match-clip")
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "source_video": str(source.resolve()),
                "clips": [{"file": clip.name}],
            }
        ),
        encoding="utf-8",
    )

    service = BackfillService(database, registry)
    dry_report = service.run(
        root=data_root,
        commit=False,
        report_path=data_root / "asset-backfill-report.json",
    )
    assert _asset_count(database) == 0
    assert any(entry.action == "create" for entry in dry_report.entries)

    first = service.run(root=data_root, commit=True)
    count_after_first = _asset_count(database)
    second = service.run(root=data_root, commit=True)

    assert _asset_count(database) == count_after_first
    assert all(entry.action == "deduplicate" for entry in second.entries)
    clip_entry = next(entry for entry in first.entries if entry.path.endswith("clip_01.mp4"))
    assert clip_entry.lifecycle_status == "internal_only"
    assert clip_entry.parent_asset_id is not None
