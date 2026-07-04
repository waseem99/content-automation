from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg.errors import CheckViolation
from pydantic import SecretStr

from src.application.assets.evidence import RightsEvidenceService
from src.application.assets.exceptions import AssetNotFound
from src.application.assets.registry import AssetRegistryService
from src.application.assets.storage import ManagedAssetStore, StorageUriResolver
from src.domain.asset_status import ApprovalStatus
from src.domain.evidence_models import RightsEvidenceType
from src.domain.voice_models import ApprovedVoiceCreate, VoiceType
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


def test_missing_evidence_target_creates_no_asset(runtime, tmp_path: Path) -> None:
    database, registry = runtime
    evidence = tmp_path / "license.pdf"
    evidence.write_bytes(b"evidence-without-target")

    with pytest.raises(AssetNotFound):
        RightsEvidenceService(database, registry).register(
            target_asset_id=uuid4(),
            evidence_path=evidence,
            evidence_type=RightsEvidenceType.LICENSE,
        )

    with database.transaction() as conn:
        asset_count = conn.execute(
            "SELECT count(*) AS total FROM football_brief.assets"
        ).fetchone()["total"]
        evidence_count = conn.execute(
            "SELECT count(*) AS total FROM football_brief.rights_evidence"
        ).fetchone()["total"]
    assert asset_count == 0
    assert evidence_count == 0


def test_evidence_target_cannot_be_its_own_evidence_asset(runtime) -> None:
    database, _ = runtime
    with pytest.raises(CheckViolation):
        with database.transaction() as conn:
            asset_id = conn.execute(
                """
                INSERT INTO football_brief.assets (
                    asset_type,
                    source_type,
                    lifecycle_status,
                    storage_uri,
                    sha256
                ) VALUES ('license_evidence', 'client_supplied', 'internal_only', %s, %s)
                RETURNING id
                """,
                ("workspace:///self-link.pdf", "a" * 64),
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO football_brief.rights_evidence (
                    asset_id,
                    evidence_asset_id,
                    evidence_type,
                    storage_uri,
                    sha256
                ) VALUES (%s, %s, 'license', %s, %s)
                """,
                (
                    asset_id,
                    asset_id,
                    "workspace:///self-link.pdf",
                    "a" * 64,
                ),
            )


def test_pending_premade_voice_round_trips(runtime) -> None:
    database, _ = runtime
    with unit_of_work(database) as uow:
        created = uow.approved_voices.create(
            ApprovedVoiceCreate(
                provider="test-provider",
                provider_voice_id="voice-001",
                display_name="Test Narrator",
                voice_type=VoiceType.PREMADE,
            )
        )
    with unit_of_work(database) as uow:
        loaded = uow.approved_voices.get_by_provider_voice_id(
            "test-provider",
            "voice-001",
        )
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.approval_status == ApprovalStatus.PENDING


def test_approved_cloned_voice_requires_consent(runtime) -> None:
    database, _ = runtime
    with pytest.raises(CheckViolation):
        with unit_of_work(database) as uow:
            uow.approved_voices.create(
                ApprovedVoiceCreate(
                    provider="test-provider",
                    provider_voice_id="clone-001",
                    display_name="Unconsented Clone",
                    voice_type=VoiceType.CLONED,
                    approval_status=ApprovalStatus.APPROVED,
                    approved_by="pytest",
                    approved_at=datetime.now(timezone.utc),
                )
            )
