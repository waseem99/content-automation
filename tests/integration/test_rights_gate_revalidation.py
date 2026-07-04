from __future__ import annotations

from pathlib import Path

import pytest

from src.application.assets.classification import AssetContext
from src.application.rights.approval import RightsApprovalService
from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint, RightsPlatform
from src.application.rights.reason_codes import RightsReasonCode
from src.application.rights.request_models import RightsGateRequest
from src.domain.asset_status import ApprovalStatus, AssetSourceType
from src.domain.rights_models import AssetRightsCreate
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import (
    approve_rights,
    close_database,
    create_workflow,
    database_fixture,
    gate_for,
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


def _request(workflow_id, asset_id, point: RightsGatePoint) -> RightsGateRequest:
    return RightsGateRequest(
        workflow_run_id=workflow_id,
        gate_point=point,
        asset_ids=(asset_id,),
        platform=RightsPlatform.YOUTUBE,
        territory="US",
        commercial_use=True,
        modification=True,
        evaluated_by="pytest",
    )


def _licensed_asset(database, tmp_path: Path, name: str):
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / f"{name}.png"
    evidence = tmp_path / "evidence" / f"{name}.pdf"
    media.parent.mkdir(parents=True, exist_ok=True)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(f"media-{name}".encode())
    evidence.write_bytes(f"evidence-{name}".encode())
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    rights = approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
    )
    return registry, media, asset, rights


def test_expiry_after_admission_blocks_render_start(database, tmp_path: Path) -> None:
    _, _, asset, rights = _licensed_asset(database, tmp_path, "expiry")
    workflow_id = create_workflow(database)
    gate = gate_for(database, tmp_path)
    admission = gate.evaluate(
        _request(workflow_id, asset.id, RightsGatePoint.MANIFEST_ADMISSION)
    )
    assert admission.outcome == RightsDecisionOutcome.PASS

    with unit_of_work(database) as uow:
        uow.rights_state.transition(
            rights_id=rights.id,
            status=ApprovalStatus.EXPIRED,
            rejection_reason="expired before render",
        )

    render = gate.evaluate(
        _request(workflow_id, asset.id, RightsGatePoint.RENDER_START)
    )
    assert render.outcome == RightsDecisionOutcome.BLOCK
    assert RightsReasonCode.RIGHTS_EXPIRED in render.reason_codes
    assert render.evaluation_id != admission.evaluation_id


def test_revocation_after_admission_blocks_render_start(database, tmp_path: Path) -> None:
    _, _, asset, rights = _licensed_asset(database, tmp_path, "revocation")
    workflow_id = create_workflow(database)
    gate = gate_for(database, tmp_path)
    assert gate.evaluate(
        _request(workflow_id, asset.id, RightsGatePoint.MANIFEST_ADMISSION)
    ).outcome == RightsDecisionOutcome.PASS

    with unit_of_work(database) as uow:
        uow.rights_state.transition(
            rights_id=rights.id,
            status=ApprovalStatus.REVOKED,
            rejection_reason="revoked before render",
        )

    render = gate.evaluate(_request(workflow_id, asset.id, RightsGatePoint.RENDER_START))
    assert RightsReasonCode.RIGHTS_REVOKED in render.reason_codes


def test_tampered_asset_bytes_block_revalidation(database, tmp_path: Path) -> None:
    _, media, asset, _ = _licensed_asset(database, tmp_path, "tamper")
    workflow_id = create_workflow(database)
    gate = gate_for(database, tmp_path)
    assert gate.evaluate(
        _request(workflow_id, asset.id, RightsGatePoint.MANIFEST_ADMISSION)
    ).outcome == RightsDecisionOutcome.PASS

    media.write_bytes(b"changed-after-admission")
    render = gate.evaluate(_request(workflow_id, asset.id, RightsGatePoint.RENDER_START))
    assert render.outcome == RightsDecisionOutcome.BLOCK
    assert render.reason_codes == (RightsReasonCode.ASSET_HASH_MISMATCH,)


def test_pending_superseding_version_prevents_old_approval_fallback(
    database,
    tmp_path: Path,
) -> None:
    _, _, asset, rights = _licensed_asset(database, tmp_path, "superseded")
    RightsApprovalService(database).create_pending(
        AssetRightsCreate(
            asset_id=asset.id,
            supersedes_rights_id=rights.id,
            rights_basis=AssetSourceType.LICENSED,
            commercial_use_allowed=True,
            modification_allowed=True,
            platforms=["youtube"],
            territories=["US"],
        )
    )

    decision = gate_for(database, tmp_path).evaluate(
        _request(create_workflow(database), asset.id, RightsGatePoint.MANIFEST_ADMISSION)
    )
    assert decision.outcome == RightsDecisionOutcome.BLOCK
    assert RightsReasonCode.RIGHTS_NOT_APPROVED in decision.reason_codes
