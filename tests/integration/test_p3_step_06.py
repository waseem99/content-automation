from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from src.application.operator_review_tools import OperatorReviewTools
from src.application.p3_step_five import P3DeliveryManifestService
from src.application.p3_step_four import P3PackageReviewService
from src.infrastructure.database.cli import app
from tests.integration.rights_support import ROOT, TEST_DSN, close_database, create_workflow, database_fixture
from tests.integration.test_p3_step_04 import _package
from tests.integration.test_p3_step_three import _plan_and_option


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


@pytest.fixture()
def cli_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DSN)
    monkeypatch.setenv("DATABASE_MIGRATIONS_DIR", str(ROOT / "migrations"))
    monkeypatch.setenv("DATABASE_REQUIRE_SCHEMA", "false")


def test_operator_queue_surfaces_p3_option_and_cli_approval(database, cli_env) -> None:
    workflow_id, _plan, option = _plan_and_option(database)
    tools = OperatorReviewTools(database)

    queue = tools.queue(workflow_id)
    option_items = [item for item in queue if item.item_type == "p3_option_review"]
    assert len(option_items) == 1
    assert option_items[0].id == option["id"]
    assert option_items[0].status == "missing"

    runner = CliRunner()
    request = runner.invoke(
        app,
        ["operator", "request-option", "--workflow-run-id", str(workflow_id), "--option-id", str(option["id"]), "--json"],
    )
    assert request.exit_code == 0
    assert json.loads(request.output)["status"] == "pending"

    approve = runner.invoke(
        app,
        [
            "operator",
            "approve-option",
            "--workflow-run-id",
            str(workflow_id),
            "--option-id",
            str(option["id"]),
            "--reviewed-by",
            "producer",
            "--json",
        ],
    )
    assert approve.exit_code == 0
    assert json.loads(approve.output)["status"] == "approved"

    queue = tools.queue(workflow_id)
    assert not [item for item in queue if item.item_type == "p3_option_review" and item.id == option["id"]]


def test_operator_cli_package_and_manifest_status(database, cli_env) -> None:
    workflow_id, package = _package(database)
    runner = CliRunner()

    status = runner.invoke(
        app,
        ["operator", "package-status", "--workflow-run-id", str(workflow_id), "--package-id", str(package.id), "--json"],
    )
    assert status.exit_code == 0
    package_payload = json.loads(status.output)
    assert package_payload["id"] == str(package.id)
    assert package_payload["review_status"] == "missing"

    request = runner.invoke(
        app,
        ["operator", "request-package", "--workflow-run-id", str(workflow_id), "--package-id", str(package.id), "--json"],
    )
    assert request.exit_code == 0
    assert json.loads(request.output)["status"] == "pending"

    approve = runner.invoke(
        app,
        [
            "operator",
            "approve-package",
            "--workflow-run-id",
            str(workflow_id),
            "--package-id",
            str(package.id),
            "--reviewed-by",
            "producer",
            "--json",
        ],
    )
    assert approve.exit_code == 0
    assert json.loads(approve.output)["status"] == "approved"

    approved_status = runner.invoke(
        app,
        ["operator", "package-status", "--workflow-run-id", str(workflow_id), "--package-id", str(package.id), "--json"],
    )
    assert approved_status.exit_code == 0
    assert json.loads(approved_status.output)["review_status"] == "approved"

    manifest_result = P3DeliveryManifestService(database).create_for_package(
        workflow_run_id=workflow_id,
        package_id=package.id,
        actor="pytest",
    )
    assert manifest_result.manifest is not None

    manifest_status = runner.invoke(app, ["operator", "manifest-status", "--workflow-run-id", str(workflow_id), "--json"])
    assert manifest_status.exit_code == 0
    manifest_payload = json.loads(manifest_status.output)
    assert manifest_payload[0]["id"] == str(manifest_result.manifest.id)
    assert manifest_payload[0]["package_id"] == str(package.id)


def test_manifest_status_can_filter_by_package(database, cli_env) -> None:
    workflow_id, package = _package(database)
    P3PackageReviewService(database).decide(
        workflow_run_id=workflow_id,
        package_id=package.id,
        status="approved",
        reviewed_by="producer",
    )
    manifest = P3DeliveryManifestService(database).create_for_package(
        workflow_run_id=workflow_id,
        package_id=package.id,
        actor="pytest",
    ).manifest
    assert manifest is not None
    other_workflow_id = create_workflow(database)

    runner = CliRunner()
    filtered = runner.invoke(
        app,
        [
            "operator",
            "manifest-status",
            "--workflow-run-id",
            str(workflow_id),
            "--package-id",
            str(package.id),
            "--json",
        ],
    )
    assert filtered.exit_code == 0
    assert [row["id"] for row in json.loads(filtered.output)] == [str(manifest.id)]

    empty = runner.invoke(app, ["operator", "manifest-status", "--workflow-run-id", str(other_workflow_id), "--json"])
    assert empty.exit_code == 0
    assert json.loads(empty.output) == []
