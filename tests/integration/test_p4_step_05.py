from __future__ import annotations

import pytest

from src.application.p3_step_five import P3DeliveryManifestService
from src.application.p4_audit import P4AuditReportService
from src.application.p4_demo_flow import P4DemoFlowService
from src.application.p4_surface import P4OperatorSurface
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


def test_audit_report_covers_blocked_demo_path(database) -> None:
    workflow_id = create_workflow(database)
    P4DemoFlowService(database).start(workflow_run_id=workflow_id)

    report = P4AuditReportService(database).report(workflow_run_id=workflow_id)

    assert report["ok"] is True
    assert report["kind"] == "audit_report"
    assert report["workflow_run_id"] == str(workflow_id)
    assert report["workflow"]["status"] == "active"
    assert report["status"]["is_blocked"] is True
    assert report["status"]["queue_count"] >= 1
    assert report["status"]["event_count"] >= 1
    assert report["timeline"]
    assert any(event["event_type"] == "research_packet_created" for event in report["timeline"])
    assert any(review["review_type"] == "packet_review" and review["status"] == "pending" for review in report["reviews"])
    assert report["queue"][0]["item_type"] == "packet_review"


def test_audit_report_tracks_reviews_after_demo_resume(database) -> None:
    workflow_id = create_workflow(database)
    demo = P4DemoFlowService(database)
    demo.start(workflow_run_id=workflow_id)
    demo.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-editor")
    demo.start(workflow_run_id=workflow_id)

    report = P4AuditReportService(database).report(workflow_run_id=workflow_id)

    assert report["ok"] is True
    assert any(review["review_type"] == "packet_review" and review["status"] == "approved" for review in report["reviews"])
    assert any(review["review_type"] == "source_output_review" and review["status"] == "pending" for review in report["reviews"])
    assert report["status"]["is_blocked"] is True
    assert "source_output_review" in report["status"]["blocked_reason"]


def test_audit_report_covers_package_and_manifest_status(database) -> None:
    workflow_id, package = _package(database)
    surface = P4OperatorSurface(database)
    approved = surface.approve_package(workflow_run_id=workflow_id, package_id=package.id, reviewed_by="producer")
    assert approved["ok"] is True
    manifest = P3DeliveryManifestService(database).create_for_package(workflow_run_id=workflow_id, package_id=package.id, actor="pytest").manifest
    assert manifest is not None

    report = P4AuditReportService(database).report(workflow_run_id=workflow_id)

    assert report["ok"] is True
    assert report["status"]["package_count"] == 1
    assert report["status"]["manifest_count"] == 1
    assert report["packages"][0]["id"] == str(package.id)
    assert report["packages"][0]["review_status"] == "approved"
    assert report["manifests"][0]["id"] == str(manifest.id)
    assert any(review["review_type"] == "package_review" and review["status"] == "approved" for review in report["reviews"])


def test_audit_report_fails_closed_for_missing_workflow(database) -> None:
    workflow_id = create_workflow(database)
    missing = workflow_id
    with database.transaction() as conn:
        conn.execute("DELETE FROM football_brief.workflow_runs WHERE id = %s", (missing,))

    report = P4AuditReportService(database).report(workflow_run_id=missing)

    assert report["ok"] is False
    assert report["kind"] == "audit_report"
    assert "workflow" in report["error"]
