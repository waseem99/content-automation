from __future__ import annotations

from pathlib import Path

import pytest

from src.application.assets.classification import AssetContext
from src.application.rights.status import RightsStatusService
from src.application.rights.supersession import RightsSupersessionService
from src.domain.asset_status import ApprovalStatus
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


def _approved(database, tmp_path: Path):
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "status.png"
    evidence = tmp_path / "evidence" / "status.pdf"
    media.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    media.write_bytes(b"status-media")
    evidence.write_bytes(b"status-evidence")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    rights = approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
    )
    return rights


def test_status_service_revokes_approved_rights(database, tmp_path: Path) -> None:
    rights = _approved(database, tmp_path)
    changed = RightsStatusService(database).revoke(rights.id, "licence withdrawn")
    assert changed.approval_status == ApprovalStatus.REVOKED
    assert changed.rejection_reason == "licence withdrawn"


def test_supersession_creates_pending_new_version(database, tmp_path: Path) -> None:
    rights = _approved(database, tmp_path)
    replacement = RightsSupersessionService(database).create_version(
        rights.id,
        {"territories": ["US"]},
    )
    assert replacement.approval_status == ApprovalStatus.PENDING
    assert replacement.supersedes_rights_id == rights.id
    assert replacement.asset_id == rights.asset_id
    assert replacement.territories == ["US"]
