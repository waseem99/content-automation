from __future__ import annotations

import pytest

from src.application.assets.classification import AssetContext
from src.application.gates import OperatorGateService, UnsafeGateDecision
from src.application.rights.enums import RightsGatePoint, RightsPlatform
from src.application.rights.request_models import RightsGateRequest
from src.domain.human_review_models import ReviewDecision, ReviewDecisionCreate, ReviewRequestCreate, ReviewTargetType
from src.domain.workflow_status import StageStatus
from tests.integration.flow_support import make_stage
from tests.integration.rights_support import close_database, create_workflow, database_fixture, gate_for, register_asset, registry_for


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_blocking_rights_result_cannot_be_marked_positive(database, tmp_path):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id, status=StageStatus.RUNNING)
    registry = registry_for(database, tmp_path)
    image = tmp_path / "unlicensed.png"
    image.write_bytes(b"unlicensed")
    asset = register_asset(registry, image, AssetContext.WEB_IMAGE_SOURCE)
    decision = gate_for(database, tmp_path).evaluate(
        RightsGateRequest(
            workflow_run_id=workflow_id,
            stage_execution_id=stage.id,
            gate_point=RightsGatePoint.MANIFEST_ADMISSION,
            asset_ids=(asset.id,),
            platform=RightsPlatform.YOUTUBE,
            territory="US",
            commercial_use=True,
            modification=True,
            evaluated_by="pytest",
        )
    )
    request = OperatorGateService(database).request_gate(
        ReviewRequestCreate(
            workflow_run_id=workflow_id,
            stage_execution_id=stage.id,
            target_type=ReviewTargetType.RIGHTS_GATE,
            target_id=decision.evaluation_id,
            review_type="rights_gate",
            requested_by="producer",
            reason="rights review",
        )
    )
    with pytest.raises(UnsafeGateDecision):
        OperatorGateService(database).record_decision(
            ReviewDecisionCreate(
                workflow_run_id=workflow_id,
                review_request_id=request.id,
                review_type="rights_gate",
                decision=ReviewDecision.APPROVED,
                reviewer="reviewer-a",
                rationale="Override requested",
                checklist={"reviewed": True},
            )
        )
