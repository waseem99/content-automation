from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from psycopg.errors import RaiseException

from src.application.quality.service import QualityGateService
from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint, RightsPlatform
from src.application.rights.reason_codes import RightsReasonCode
from src.application.rights.request_models import RightsGateRequest
from src.application.workers.models import WorkerExecutionRequest, WorkerOutcome
from src.domain.budget_models import BudgetLimit
from src.domain.quality_models import QualityOutcome
from src.infrastructure.database.uow import unit_of_work
from tests.integration.budget_support import budgeted_dispatcher
from tests.integration.quality_support import publish_manifest_and_job
from tests.integration.rights_support import close_database, create_workflow, database_fixture, gate_for, register_asset, registry_for


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _rights_request(workflow_id, asset_id) -> RightsGateRequest:
    return RightsGateRequest(
        workflow_run_id=workflow_id,
        gate_point=RightsGatePoint.MANIFEST_ADMISSION,
        asset_ids=(asset_id,),
        platform=RightsPlatform.YOUTUBE,
        territory="US",
        commercial_use=True,
        modification=True,
        evaluated_by="pytest",
    )


def _provider_request(workflow_id) -> WorkerExecutionRequest:
    return WorkerExecutionRequest(
        workflow_run_id=workflow_id,
        worker_name="demo_worker",
        worker_version="1",
        input_payload={"value": "blocked-by-budget"},
        actor="pytest",
        provider="openai",
        operation="image",
        provider_model_id="standard",
        provider_units=Decimal("1"),
    )


def test_foundation_negative_pilot_blocks_publish_risks_before_release(database, tmp_path: Path) -> None:
    registry = registry_for(database, tmp_path)
    media = tmp_path / "data" / "input" / "match.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"unapproved-source-match")
    asset = register_asset(registry, media, context=__import__("src.application.assets.classification", fromlist=["AssetContext"]).AssetContext.SOURCE_MATCH_VIDEO)

    rights_decision = gate_for(database, tmp_path).evaluate(_rights_request(create_workflow(database), asset.id))
    assert rights_decision.outcome == RightsDecisionOutcome.BLOCK
    assert RightsReasonCode.UNAPPROVED_MATCH_FOOTAGE in rights_decision.reason_codes

    workflow_id = create_workflow(database)
    service, _budget, handler = budgeted_dispatcher(database, limits=BudgetLimit(workflow_limit_usd=Decimal("0.0100")))
    budget_result = service.execute(_provider_request(workflow_id))
    assert budget_result.outcome == WorkerOutcome.FAILED
    assert handler.calls == 0
    with unit_of_work(database) as uow:
        event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'budget_stopped'",
            (workflow_id,),
        ).fetchone()
    assert event is not None

    no_audio_metadata = {"media": {"valid_container": True, "width": 1080, "height": 1920, "fps": 30, "duration_sec": 30, "has_audio": False}}
    _registry, resolver, manifest, job, _asset, _output = publish_manifest_and_job(database, tmp_path / "quality", output_metadata=no_audio_metadata)
    report = QualityGateService(database=database, resolver=resolver).evaluate_render_job(job["id"], created_by="pytest")
    assert report.overall_status == QualityOutcome.HUMAN_REVIEW_REQUIRED
    assert "AUDIO_MISSING" in report.human_review_reasons

    with pytest.raises(RaiseException, match="passing quality report"):
        with unit_of_work(database) as uow:
            uow.release_references.create(
                manifest_id=manifest.id,
                render_job_id=job["id"],
                package_hash="d" * 64,
                created_by="pytest",
            )
