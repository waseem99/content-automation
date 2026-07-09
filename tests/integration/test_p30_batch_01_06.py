from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p30_analytics import (
    FUTURE_API_CANDIDATES,
    FUTURE_API_SAFEGUARDS,
    ITERATION_ELEMENT_TYPES,
    METRIC_FIELDS,
    OUTCOME_LABELS,
    P28_SCORE_LINKS,
    RECOMMENDATION_OUTPUTS,
    SUPPORTED_FORMATS,
    SUPPORTED_PLATFORMS,
    build_p30_analytics_feedback_contract,
    validate_p30_analytics_feedback_contract,
)


pytestmark = pytest.mark.integration

EXAMPLE_PATH = Path("docs/operations/p30-analytics-feedback-example.json")
CHECKLIST_PATH = Path("docs/operations/p30-closeout-checklist.json")
REPORT_PATH = Path("docs/operations/p30-closeout-report.md")
DOC_PATHS = [
    Path("docs/operations/p30-step-01.md"),
    Path("docs/operations/p30-step-02.md"),
    Path("docs/operations/p30-step-03.md"),
    Path("docs/operations/p30-step-04.md"),
    Path("docs/operations/p30-step-05.md"),
    Path("docs/operations/p30-step-06.md"),
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p30_docs_exist_and_reference_child_issues() -> None:
    expected = {
        "docs/operations/p30-step-01.md": ["Closes #412", "performance metrics input contract", "no live API ingestion"],
        "docs/operations/p30-step-02.md": ["Closes #413", "learning snapshot", "outperforming"],
        "docs/operations/p30-step-03.md": ["Closes #414", "topic-score feedback", "repeat_format"],
        "docs/operations/p30-step-04.md": ["Closes #415", "packaging", "review_required"],
        "docs/operations/p30-step-05.md": ["Closes #416", "future analytics API boundary", "manual or fixture-based metrics only"],
        "docs/operations/p30-step-06.md": ["Closes #417", "P30", "no live analytics ingestion"],
    }
    for path in DOC_PATHS:
        assert path.exists(), path
    for path_str, terms in expected.items():
        content = Path(path_str).read_text(encoding="utf-8")
        for term in terms:
            assert term in content


def test_generated_p30_contract_is_valid() -> None:
    contract = build_p30_analytics_feedback_contract()
    result = validate_p30_analytics_feedback_contract(contract)

    assert result["schema_version"] == "p30.analytics_feedback_validation.v1"
    assert result["is_valid"] is True
    assert result["errors"] == []
    assert result["metrics_fields_checked"] == list(METRIC_FIELDS)
    assert result["recommendation_outputs_checked"] == list(RECOMMENDATION_OUTPUTS)
    assert result["publish_allowed"] is False
    assert result["review_required"] is True


def test_p30_example_contract_is_valid() -> None:
    example = _read_json(EXAMPLE_PATH)
    result = validate_p30_analytics_feedback_contract(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == "p30.analytics_feedback.v1"
    assert example["parent_epic"] == 411
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_p30_metrics_contract_required_fields_formats_and_platforms() -> None:
    contract = build_p30_analytics_feedback_contract()
    metrics = contract["metrics_input_contract"]

    assert set(METRIC_FIELDS) <= set(metrics["required_fields"])
    assert set(SUPPORTED_FORMATS) <= set(metrics["supported_formats"])
    assert set(SUPPORTED_PLATFORMS) <= set(metrics["supported_platforms"])
    for record in metrics["records"]:
        assert set(METRIC_FIELDS) <= set(record)
        assert record["live_api_ingested"] is False
        assert record["credential_storage_used"] is False


def test_p30_learning_snapshots_cover_required_outcomes() -> None:
    contract = build_p30_analytics_feedback_contract()
    snapshots = contract["learning_snapshot_contract"]

    assert set(OUTCOME_LABELS) <= set(snapshots["outcome_labels"])
    labels = {snapshot["outcome_label"] for snapshot in snapshots["snapshots"]}
    assert "outperforming" in labels
    assert "average" in labels
    assert "blocked_from_learning" in labels


def test_p30_feedback_rules_link_to_p28_scores_and_require_human_review() -> None:
    contract = build_p30_analytics_feedback_contract()
    feedback = contract["topic_feedback_rules"]

    assert set(P28_SCORE_LINKS) <= set(feedback["p28_score_links"])
    assert set(RECOMMENDATION_OUTPUTS) <= set(feedback["recommendation_outputs"])
    for rule in feedback["rules"]:
        assert rule["then"] in RECOMMENDATION_OUTPUTS
        assert rule["requires_human_review"] is True


def test_p30_iteration_contract_covers_hook_title_and_thumbnail() -> None:
    contract = build_p30_analytics_feedback_contract()
    iteration = contract["packaging_iteration_contract"]

    assert set(ITERATION_ELEMENT_TYPES) <= set(iteration["element_types"])
    elements = {item["element_type"] for item in iteration["recommendations"]}
    assert "hook" in elements
    assert "title" in elements
    assert "thumbnail_cover" in elements
    for item in iteration["recommendations"]:
        assert item["review_status"] == "review_required"


def test_p30_future_api_boundary_is_safe() -> None:
    contract = build_p30_analytics_feedback_contract()
    boundary = contract["future_api_boundary"]

    assert set(FUTURE_API_CANDIDATES) <= set(boundary["api_candidates"])
    assert set(FUTURE_API_SAFEGUARDS) <= set(boundary["required_safeguards"])
    assert boundary["current_support"] == "manual_or_fixture_metrics_only"
    assert boundary["live_api_ingestion_enabled"] is False
    assert boundary["oauth_implemented"] is False
    assert boundary["credential_storage_used"] is False
    assert boundary["real_account_data_ingested"] is False


def test_p30_validation_catches_live_api_and_credential_regressions() -> None:
    contract = build_p30_analytics_feedback_contract()
    contract["metrics_input_contract"]["records"][0]["live_api_ingested"] = True
    contract["metrics_input_contract"]["records"][0]["credential_storage_used"] = True
    contract["future_api_boundary"]["live_api_ingestion_enabled"] = True
    contract["future_api_boundary"]["credential_storage_used"] = True

    result = validate_p30_analytics_feedback_contract(contract)

    assert result["is_valid"] is False
    assert "live API ingestion must remain false" in result["errors"]
    assert "credential storage must remain false" in result["errors"]
    assert "live API ingestion must remain disabled" in result["errors"]


def test_p30_validation_catches_missing_recommendation_and_iteration_fields() -> None:
    contract = build_p30_analytics_feedback_contract()
    contract["topic_feedback_rules"]["recommendation_outputs"].remove("hold")
    contract["packaging_iteration_contract"]["recommendations"][0]["review_status"] = "approved_without_review"

    result = validate_p30_analytics_feedback_contract(contract)

    assert result["is_valid"] is False
    assert "recommendation outputs missing" in result["errors"]
    assert "iteration recommendation must require review" in result["errors"]


def test_p30_closeout_report_and_checklist_cover_guardrails() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    checklist = _read_json(CHECKLIST_PATH)

    for issue in ["#412", "#413", "#414", "#415", "#416", "#417"]:
        assert issue in report
    for guardrail in [
        "No live analytics ingestion.",
        "No API credential storage.",
        "No OAuth flows.",
        "No real account data ingestion.",
        "No automated topic creation.",
        "No automated packaging changes.",
        "No automated publishing decisions.",
        "No direct platform edits.",
        "No direct platform uploads.",
        "No paid media optimization.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in checklist["guardrails"]

    assert checklist["child_tasks"]
    assert [task["issue"] for task in checklist["child_tasks"]] == [412, 413, 414, 415, 416, 417]
    assert checklist["no_live_analytics_ingestion"] is True
    assert checklist["no_api_credential_storage"] is True
    assert checklist["no_auto_publish_path"] is True
    assert checklist["human_review_required"] is True


def test_p30_contract_output_is_deterministic() -> None:
    assert build_p30_analytics_feedback_contract() == build_p30_analytics_feedback_contract()
