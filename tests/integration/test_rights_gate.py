from __future__ import annotations

from pathlib import Path

import pytest
from psycopg.errors import RaiseException

from src.application.assets.classification import AssetContext
from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint, RightsPlatform
from src.application.rights.reason_codes import RightsReasonCode
from src.application.rights.request_models import RightsGateRequest
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


def _request(workflow_id, asset_id, **updates) -> RightsGateRequest:
    values = {
        "workflow_run_id": workflow_id,
        "gate_point": RightsGatePoint.MANIFEST_ADMISSION,
        "asset_ids": (asset_id,),
        "platform": RightsPlatform.YOUTUBE,
        "territory": "US",
        "commercial_use": True,
        "modification": True,
        "evaluated_by": "pytest",
    }
    values.update(updates)
    return RightsGateRequest(**values)


def test_unapproved_match_footage_blocks_and_is_audited(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "input" / "match.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"broadcast-footage")
    asset = register_asset(
        registry,
        media,
        AssetContext.SOURCE_MATCH_VIDEO,
        metadata={"pipeline_role": "source_match_video"},
    )
    workflow_id = create_workflow(database)

    decision = gate_for(database, tmp_path).evaluate(_request(workflow_id, asset.id))

    assert decision.outcome == RightsDecisionOutcome.BLOCK
    assert RightsReasonCode.UNAPPROVED_MATCH_FOOTAGE in decision.reason_codes
    with database.transaction() as conn:
        evaluation = conn.execute(
            "SELECT * FROM football_brief.rights_gate_evaluations WHERE id = %s",
            (decision.evaluation_id,),
        ).fetchone()
        asset_decision = conn.execute(
            "SELECT * FROM football_brief.rights_gate_asset_decisions WHERE evaluation_id = %s",
            (decision.evaluation_id,),
        ).fetchone()
    assert evaluation["policy_version"] == "1.0.0"
    assert evaluation["outcome"] == "block"
    assert asset_decision["asset_sha256"] == asset.sha256


def test_complete_match_footage_rights_pass(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "input" / "licensed-match.mp4"
    evidence = tmp_path / "evidence" / "match-license.pdf"
    media.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    media.write_bytes(b"licensed-match")
    evidence.write_bytes(b"license-evidence")
    asset = register_asset(
        registry,
        media,
        AssetContext.SOURCE_MATCH_VIDEO,
        metadata={"source_category": "broadcast_footage"},
    )
    approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
        platforms=["youtube"],
        territories=["US"],
    )

    decision = gate_for(database, tmp_path).evaluate(
        _request(create_workflow(database), asset.id)
    )
    assert decision.outcome == RightsDecisionOutcome.PASS


def test_platform_and_territory_scope_are_exact(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "image.png"
    evidence = tmp_path / "evidence" / "image-license.pdf"
    media.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    media.write_bytes(b"image")
    evidence.write_bytes(b"license")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
        platforms=["youtube"],
        territories=["US"],
    )
    gate = gate_for(database, tmp_path)

    wrong_platform = gate.evaluate(
        _request(
            create_workflow(database),
            asset.id,
            platform=RightsPlatform.FACEBOOK,
        )
    )
    wrong_territory = gate.evaluate(
        _request(create_workflow(database), asset.id, territory="CA")
    )
    assert RightsReasonCode.PLATFORM_NOT_ALLOWED in wrong_platform.reason_codes
    assert RightsReasonCode.TERRITORY_NOT_ALLOWED in wrong_territory.reason_codes


def test_worldwide_rights_pass_multiple_territories(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "world.png"
    evidence = tmp_path / "evidence" / "world-license.pdf"
    media.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    media.write_bytes(b"world-image")
    evidence.write_bytes(b"world-license")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    approve_rights(
        database=database,
        registry=registry,
        asset_id=asset.id,
        evidence_path=evidence,
        territories=["worldwide"],
    )
    gate = gate_for(database, tmp_path)
    for territory in ("US", "CA"):
        decision = gate.evaluate(
            _request(create_workflow(database), asset.id, territory=territory)
        )
        assert decision.outcome == RightsDecisionOutcome.PASS


def test_unapproved_web_image_and_missing_attribution_block(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    unapproved_path = tmp_path / "data" / "candidate.png"
    attributed_path = tmp_path / "data" / "attributed.png"
    evidence = tmp_path / "evidence" / "attribution-license.pdf"
    unapproved_path.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    unapproved_path.write_bytes(b"candidate")
    attributed_path.write_bytes(b"attributed")
    evidence.write_bytes(b"attribution-license")
    unapproved = register_asset(registry, unapproved_path, AssetContext.WEB_IMAGE_SOURCE)
    attributed = register_asset(registry, attributed_path, AssetContext.WEB_IMAGE_SOURCE)
    approve_rights(
        database=database,
        registry=registry,
        asset_id=attributed.id,
        evidence_path=evidence,
        attribution_required=True,
        attribution_text="Photo: Rights Holder",
    )
    gate = gate_for(database, tmp_path)

    first = gate.evaluate(_request(create_workflow(database), unapproved.id))
    second = gate.evaluate(_request(create_workflow(database), attributed.id))
    assert RightsReasonCode.RIGHTS_NOT_APPROVED in first.reason_codes
    assert RightsReasonCode.ATTRIBUTION_MISSING in second.reason_codes


def test_audit_rows_reject_mutation(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "audit.png"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"audit")
    asset = register_asset(registry, media, AssetContext.WEB_IMAGE_SOURCE)
    decision = gate_for(database, tmp_path).evaluate(
        _request(create_workflow(database), asset.id)
    )

    with pytest.raises(RaiseException, match="append-only"):
        with database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.rights_gate_evaluations SET evaluated_by = 'changed' "
                "WHERE id = %s",
                (decision.evaluation_id,),
            )
