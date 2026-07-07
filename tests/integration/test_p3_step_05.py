from __future__ import annotations

import pytest

from src.application.p3_step_four import P3PackageReviewService, P3StepFourError
from src.application.p3_step_five import P3DeliveryManifestService
from src.application.workers.models import WorkerOutcome
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import close_database, create_workflow, database_fixture
from tests.integration.test_p3_step_04 import _package


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_missing_final_approval_blocks_manifest_generation(database) -> None:
    workflow_id, package = _package(database)

    with pytest.raises(P3StepFourError, match="missing"):
        P3DeliveryManifestService(database).create_for_package(
            workflow_run_id=workflow_id,
            package_id=package.id,
            actor="pytest",
        )


def test_approved_package_creates_delivery_manifest(database) -> None:
    workflow_id, package = _package(database)
    P3PackageReviewService(database).decide(
        workflow_run_id=workflow_id,
        package_id=package.id,
        status="approved",
        reviewed_by="producer",
        rationale="ready",
        decision_metadata={"checklist": "complete"},
    )

    result = P3DeliveryManifestService(database).create_for_package(
        workflow_run_id=workflow_id,
        package_id=package.id,
        actor="pytest",
    )

    assert result.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert result.manifest is not None
    assert result.manifest.workflow_run_id == workflow_id
    assert result.manifest.package_id == package.id
    assert result.manifest.step_plan_id == package.step_plan_id
    assert result.manifest.manifest["package_id"] == str(package.id)
    assert result.manifest.manifest["step_plan_id"] == str(package.step_plan_id)
    assert result.manifest.manifest["selected_asset_ids"] == package.option_ids
    assert result.manifest.approval_metadata["status"] == "approved"
    assert result.manifest.approval_metadata["decision_metadata"]["checklist"] == "complete"
    assert result.manifest.lineage_refs["package_id"] == str(package.id)
    assert result.manifest.package_metadata["option_count"] == 1

    with unit_of_work(database) as uow:
        event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'p3_delivery_manifest_created'",
            (workflow_id,),
        ).fetchone()
    assert event is not None
    assert event["payload"]["manifest_id"] == str(result.manifest.id)


def test_duplicate_manifest_request_reuses_existing_manifest(database) -> None:
    workflow_id, package = _package(database)
    P3PackageReviewService(database).decide(
        workflow_run_id=workflow_id,
        package_id=package.id,
        status="approved",
        reviewed_by="producer",
    )
    service = P3DeliveryManifestService(database)

    first = service.create_for_package(workflow_run_id=workflow_id, package_id=package.id, actor="pytest")
    second = service.create_for_package(workflow_run_id=workflow_id, package_id=package.id, actor="pytest")

    assert first.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert second.worker_result.outcome == WorkerOutcome.REUSED
    assert first.manifest is not None and second.manifest is not None
    assert second.manifest.id == first.manifest.id
    with unit_of_work(database) as uow:
        count = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.p3_delivery_manifests").fetchone()["count"]
    assert count == 1


def test_wrong_workflow_manifest_input_fails_closed(database) -> None:
    workflow_id, package = _package(database)
    other_workflow_id = create_workflow(database)
    P3PackageReviewService(database).decide(
        workflow_run_id=workflow_id,
        package_id=package.id,
        status="approved",
        reviewed_by="producer",
    )

    with pytest.raises(P3StepFourError, match="package"):
        P3DeliveryManifestService(database).create_for_package(
            workflow_run_id=other_workflow_id,
            package_id=package.id,
            actor="pytest",
        )
