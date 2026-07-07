from __future__ import annotations

import pytest

from src.application.operator_review_tools import OperatorReviewTools
from src.application.p3_step_four import P3PackageReviewService, P3StepFourError
from src.application.p3_step_three import P3PackageService, P3PlanReviewService
from src.application.p3_step_two import P3StepTwoService
from tests.integration.rights_support import close_database, create_workflow, database_fixture
from tests.integration.test_p3_step_three import _plan_and_option


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _package(database):
    workflow_id, plan, option = _plan_and_option(database)
    P3PlanReviewService(database).decide(workflow_run_id=workflow_id, step_plan_id=plan.id, status="approved", reviewed_by="producer")
    P3StepTwoService(database).decide(workflow_run_id=workflow_id, option_id=option["id"], status="approved", reviewed_by="producer")
    result = P3PackageService(database).create_for_plan(workflow_run_id=workflow_id, step_plan_id=plan.id, option_ids=[option["id"]], actor="pytest")
    assert result.package is not None
    return workflow_id, result.package


def test_missing_pending_and_returned_review_block_next_step(database) -> None:
    workflow_id, package = _package(database)
    service = P3PackageReviewService(database)

    with pytest.raises(P3StepFourError, match="missing"):
        service.require_approved(workflow_run_id=workflow_id, package_id=package.id)

    review = service.request_review(workflow_run_id=workflow_id, package_id=package.id, actor="pytest")
    assert review.status == "pending"
    assert service.pending(workflow_id)[0].id == review.id

    with pytest.raises(P3StepFourError, match="not approved"):
        service.require_approved(workflow_run_id=workflow_id, package_id=package.id)

    returned = service.decide(workflow_run_id=workflow_id, package_id=package.id, status="returned", reviewed_by="producer", rationale="needs changes")
    assert returned.status == "returned"
    with pytest.raises(P3StepFourError, match="not approved"):
        service.require_approved(workflow_run_id=workflow_id, package_id=package.id)


def test_approved_package_can_be_consumed(database) -> None:
    workflow_id, package = _package(database)
    service = P3PackageReviewService(database)
    service.request_review(workflow_run_id=workflow_id, package_id=package.id, actor="pytest")

    decision = service.decide(workflow_run_id=workflow_id, package_id=package.id, status="approved", reviewed_by="producer", rationale="ready", decision_metadata={"checklist": "complete"})
    approved = service.require_approved(workflow_run_id=workflow_id, package_id=package.id)

    assert decision.status == "approved"
    assert decision.decision_metadata["checklist"] == "complete"
    assert approved["id"] == package.id
    assert approved["package_hash"] == package.package_hash


def test_operator_queue_surfaces_package_review_item(database) -> None:
    workflow_id, package = _package(database)

    queue = OperatorReviewTools(database).queue(workflow_id)
    package_items = [item for item in queue if item.item_type == "package_review"]
    assert len(package_items) == 1
    assert package_items[0].id == package.id
    assert package_items[0].status == "missing"

    P3PackageReviewService(database).request_review(workflow_run_id=workflow_id, package_id=package.id, actor="pytest")
    queue = OperatorReviewTools(database).queue(workflow_id)
    package_items = [item for item in queue if item.item_type == "package_review"]
    assert len(package_items) == 1
    assert package_items[0].status == "pending"


def test_wrong_workflow_and_invalid_status_fail_closed(database) -> None:
    workflow_id, package = _package(database)
    other_workflow_id = create_workflow(database)
    service = P3PackageReviewService(database)

    with pytest.raises(P3StepFourError, match="package"):
        service.request_review(workflow_run_id=other_workflow_id, package_id=package.id, actor="pytest")

    with pytest.raises(P3StepFourError, match="status"):
        service.decide(workflow_run_id=workflow_id, package_id=package.id, status="pending", reviewed_by="producer")
