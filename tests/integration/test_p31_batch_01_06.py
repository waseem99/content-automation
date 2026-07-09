from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p31_reporting import (
    DECISION_TYPES,
    EXCEPTION_FIELDS,
    HANDOFF_FILES,
    REPORTING_INPUT_FIELDS,
    SEVERITY_LEVELS,
    UPSTREAM_LINKS,
    WEEKLY_BRIEF_FIELDS,
    build_p31_operator_reporting_contract,
    validate_p31_operator_reporting_contract,
)


pytestmark = pytest.mark.integration

EXAMPLE_PATH = Path("docs/operations/p31-operator-reporting-example.json")
CHECKLIST_PATH = Path("docs/operations/p31-closeout-checklist.json")
REPORT_PATH = Path("docs/operations/p31-closeout-report.md")
DOC_PATHS = [
    Path("docs/operations/p31-step-01.md"),
    Path("docs/operations/p31-step-02.md"),
    Path("docs/operations/p31-step-03.md"),
    Path("docs/operations/p31-step-04.md"),
    Path("docs/operations/p31-step-05.md"),
    Path("docs/operations/p31-step-06.md"),
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p31_docs_exist_and_reference_child_issues() -> None:
    expected = {
        "docs/operations/p31-step-01.md": ["Closes #420", "reporting input bundle", "P27 export packs"],
        "docs/operations/p31-step-02.md": ["Closes #421", "weekly channel performance brief", "not an automated analytics dashboard"],
        "docs/operations/p31-step-03.md": ["Closes #422", "content decision queue", "No action is automatically executed"],
        "docs/operations/p31-step-04.md": ["Closes #423", "risk and governance exception report", "automatic publishing"],
        "docs/operations/p31-step-05.md": ["Closes #424", "operator handoff", "No email, Slack, dashboard"],
        "docs/operations/p31-step-06.md": ["Closes #425", "P31", "no auto-publish path"],
    }
    for path in DOC_PATHS:
        assert path.exists(), path
    for path_str, terms in expected.items():
        content = Path(path_str).read_text(encoding="utf-8")
        for term in terms:
            assert term in content


def test_generated_p31_contract_is_valid() -> None:
    contract = build_p31_operator_reporting_contract()
    result = validate_p31_operator_reporting_contract(contract)

    assert result["schema_version"] == "p31.operator_reporting_validation.v1"
    assert result["is_valid"] is True
    assert result["errors"] == []
    assert result["reporting_input_fields_checked"] == list(REPORTING_INPUT_FIELDS)
    assert result["weekly_brief_fields_checked"] == list(WEEKLY_BRIEF_FIELDS)
    assert result["exception_fields_checked"] == list(EXCEPTION_FIELDS)
    assert result["publish_allowed"] is False
    assert result["review_required"] is True


def test_p31_example_contract_is_valid() -> None:
    example = _read_json(EXAMPLE_PATH)
    result = validate_p31_operator_reporting_contract(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == "p31.operator_reporting.v1"
    assert example["parent_epic"] == 419
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_reporting_input_bundle_links_upstream_artifacts_and_has_safety_flags() -> None:
    contract = build_p31_operator_reporting_contract()
    bundle = contract["reporting_input_bundle"]
    example = bundle["example"]

    assert set(REPORTING_INPUT_FIELDS) <= set(bundle["required_fields"])
    assert set(UPSTREAM_LINKS) <= set(bundle["upstream_links"])
    assert set(REPORTING_INPUT_FIELDS) <= set(example)
    assert example["manual_or_fixture_based"] is True
    assert example["live_api_ingested"] is False
    assert example["automated_notification_sent"] is False


def test_weekly_brief_has_required_sections_and_no_dashboard_delivery() -> None:
    contract = build_p31_operator_reporting_contract()
    brief = contract["weekly_channel_brief"]
    example = brief["example"]

    assert set(WEEKLY_BRIEF_FIELDS) <= set(brief["required_fields"])
    assert set(WEEKLY_BRIEF_FIELDS) <= set(example)
    assert example["not_dashboard"] is True
    assert example["automated_delivery"] is False
    assert example["top_performers"]
    assert example["review_required_items"]


def test_decision_queue_covers_supported_decisions_and_never_executes_automatically() -> None:
    contract = build_p31_operator_reporting_contract()
    queue = contract["content_decision_queue"]

    assert set(DECISION_TYPES) <= set(queue["decision_types"])
    seen_types = {item["decision_type"] for item in queue["items"]}
    assert {"repeat", "revise", "archive"} <= seen_types
    for item in queue["items"]:
        assert item["decision_type"] in DECISION_TYPES
        assert item["review_status"] == "review_required"
        assert item["automatically_executed"] is False


def test_governance_exceptions_cover_severity_and_do_not_trigger_platform_action() -> None:
    contract = build_p31_operator_reporting_contract()
    exceptions = contract["risk_governance_exceptions"]

    assert set(EXCEPTION_FIELDS) <= set(exceptions["required_fields"])
    assert set(SEVERITY_LEVELS) <= set(exceptions["severity_levels"])
    for exception in exceptions["exceptions"]:
        assert set(EXCEPTION_FIELDS) <= set(exception)
        assert exception["severity"] in SEVERITY_LEVELS
        assert exception["automatic_platform_action"] is False


def test_operator_handoff_package_has_required_files_and_is_review_only() -> None:
    contract = build_p31_operator_reporting_contract()
    handoff = contract["operator_handoff_package"]
    example = handoff["example"]

    assert set(HANDOFF_FILES) <= set(handoff["required_files"])
    assert set(HANDOFF_FILES) <= set(example["files"])
    assert example["review_required"] is True
    assert example["external_distribution_performed"] is False
    assert "No email" in example["distribution_note"]


def test_p31_validation_catches_dashboard_api_and_distribution_regressions() -> None:
    contract = build_p31_operator_reporting_contract()
    contract["weekly_channel_brief"]["example"]["not_dashboard"] = False
    contract["reporting_input_bundle"]["example"]["live_api_ingested"] = True
    contract["operator_handoff_package"]["example"]["external_distribution_performed"] = True

    result = validate_p31_operator_reporting_contract(contract)

    assert result["is_valid"] is False
    assert "weekly brief must not be dashboard" in result["errors"]
    assert "bundle must not ingest live APIs" in result["errors"]
    assert "handoff must not distribute externally" in result["errors"]


def test_p31_validation_catches_auto_execution_regressions() -> None:
    contract = build_p31_operator_reporting_contract()
    contract["content_decision_queue"]["items"][0]["automatically_executed"] = True
    contract["risk_governance_exceptions"]["exceptions"][0]["automatic_platform_action"] = True
    contract["closeout"]["no_auto_publish_path"] = False

    result = validate_p31_operator_reporting_contract(contract)

    assert result["is_valid"] is False
    assert "decision item must not execute automatically" in result["errors"]
    assert "exception must not trigger platform action" in result["errors"]
    assert "auto-publish exclusion missing" in result["errors"]


def test_p31_closeout_report_and_checklist_cover_guardrails() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    checklist = _read_json(CHECKLIST_PATH)

    for issue in ["#420", "#421", "#422", "#423", "#424", "#425"]:
        assert issue in report

    for guardrail in [
        "No dashboard UI.",
        "No automated email/Slack reporting.",
        "No live API ingestion.",
        "No real account sync.",
        "No automatic task creation.",
        "No automatic scheduling.",
        "No external distribution.",
        "No platform uploads.",
        "No automated publishing decisions.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]

    assert [task["issue"] for task in checklist["child_tasks"]] == [420, 421, 422, 423, 424, 425]
    assert checklist["no_dashboard_ui"] is True
    assert checklist["no_email_slack_automation"] is True
    assert checklist["no_live_api_ingestion"] is True
    assert checklist["no_external_distribution"] is True
    assert checklist["no_auto_publish_path"] is True


def test_p31_contract_output_is_deterministic() -> None:
    assert build_p31_operator_reporting_contract() == build_p31_operator_reporting_contract()
