from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from psycopg.errors import RaiseException

from src.application.assets.classification import AssetContext
from src.application.assets.evidence import RightsEvidenceService
from src.application.rights.approval import RightsApprovalService
from src.domain.asset_status import ApprovalStatus, AssetSourceType
from src.domain.evidence_models import RightsEvidenceType
from src.domain.rights_models import AssetRightsCreate
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import (
    approve_rights,
    close_database,
    database_fixture,
    register_asset,
    registry_for,
)


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_approved_rights_cannot_commit_without_linked_evidence(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "image.png"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"image")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)

    with pytest.raises(RaiseException, match="linked evidence"):
        with unit_of_work(database) as uow:
            uow.asset_rights.create(
                AssetRightsCreate(
                    asset_id=asset.id,
                    rights_basis=AssetSourceType.LICENSED,
                    commercial_use_allowed=True,
                    modification_allowed=True,
                    platforms=["youtube"],
                    territories=["worldwide"],
                    approval_status=ApprovalStatus.APPROVED,
                    approved_by="pytest",
                    approved_at=datetime.now(timezone.utc),
                )
            )


def test_evidence_for_another_asset_cannot_support_rights(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    first_path = tmp_path / "data" / "first.png"
    second_path = tmp_path / "data" / "second.png"
    evidence_path = tmp_path / "evidence" / "license.pdf"
    first_path.parent.mkdir(parents=True)
    evidence_path.parent.mkdir(parents=True)
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    evidence_path.write_bytes(b"license")
    first = register_asset(registry, first_path, AssetContext.WEB_IMAGE_SOURCE)
    second = register_asset(registry, second_path, AssetContext.WEB_IMAGE_SOURCE)

    approvals = RightsApprovalService(database)
    rights = approvals.create_pending(
        AssetRightsCreate(
            asset_id=first.id,
            rights_basis=AssetSourceType.LICENSED,
            commercial_use_allowed=True,
            platforms=["youtube"],
            territories=["worldwide"],
        )
    )
    evidence = RightsEvidenceService(database, registry).register(
        target_asset_id=second.id,
        evidence_path=evidence_path,
        evidence_type=RightsEvidenceType.LICENSE,
        uploaded_by="pytest",
    )

    with pytest.raises(RaiseException, match="same asset"):
        approvals.link_evidence(
            rights_id=rights.id,
            evidence_id=evidence.id,
            evidence_role="license",
            linked_by="pytest",
        )


def test_approved_rights_cannot_lose_last_evidence(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "licensed.png"
    evidence = tmp_path / "evidence" / "license.pdf"
    media.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    media.write_bytes(b"licensed")
    evidence.write_bytes(b"evidence")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    rights = approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
    )

    with pytest.raises(RaiseException, match="linked evidence"):
        with database.transaction() as conn:
            conn.execute(
                "DELETE FROM football_brief.asset_rights_evidence_links "
                "WHERE asset_rights_id = %s",
                (rights.id,),
            )


def test_pending_superseding_version_belongs_to_same_asset(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "original.png"
    evidence = tmp_path / "evidence" / "license.pdf"
    media.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    media.write_bytes(b"original")
    evidence.write_bytes(b"evidence")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    previous = approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
    )

    replacement = RightsApprovalService(database).create_pending(
        AssetRightsCreate(
            asset_id=asset.id,
            supersedes_rights_id=previous.id,
            rights_basis=AssetSourceType.LICENSED,
            platforms=["youtube"],
            territories=["US"],
        )
    )
    assert replacement.supersedes_rights_id == previous.id
    assert replacement.approval_status == ApprovalStatus.PENDING
