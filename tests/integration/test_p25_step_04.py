from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.retention_score import (
    REPORT_SCHEMA_VERSION,
    apply_retention_score_to_package,
    build_retention_score_report,
    write_retention_score_report,
)


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p25-step-04.md")
EXAMPLE = Path("docs/operations/p25-retention-score-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_FIELDS = {
    "schema_version",
    "package_id",
    "content_type",
    "source_topic",
    "hook_text",
    "cta_text",
    "hook_score",
    "first_1s_thumb_stop_score",
    "first_3s_clarity_score",
    "first_8s_retention_lock_score",
    "curiosity_gap_score",
    "visual_pacing_score",
    "midpoint_reset_score",
    "cta_strength_score",
    "average_core_score",
    "dead_air_risk",
    "genericness_risk",
    "recommended_fixes",
    "status",
    "approval_state",
    "planned_epic",
    "notes",
}

RISK_LABELS = {"low", "medium", "high"}


def test_p25_retention_report_contract_references_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #327. Closes #341 after the PR merges.",
        "docs/operations/p24-step-03.md",
        "docs/operations/p24-step-05.md",
        "docs/operations/p25-step-01.md",
        "docs/operations/p25-step-02.md",
        "docs/operations/p25-step-03.md",
        "src/content_package.py",
        "src/retention_score.py",
        "docs/operations/p25-retention-score-example.json",
        "tests/integration/test_p25_step_04.py",
        "define `retention_score.json` schema",
        "generate placeholder scores for hook strength",
        "generate `dead_air_risk`",
        "generate `genericness_risk`",
        "provide a package integration helper",
        "does not ingest YouTube Analytics",
        "does not run A/B tests",
        "does not call AI scoring services",
        "does not predict real retention curves",
        "does not approve publishing",
        "does not upload to YouTube",
        "does not publish content",
    ]:
        assert term in content


def test_p25_retention_report_schema_fields_and_risk_labels_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "schema_version",
        "package_id",
        "content_type",
        "source_topic",
        "hook_text",
        "cta_text",
        "hook_score",
        "first_1s_thumb_stop_score",
        "first_3s_clarity_score",
        "first_8s_retention_lock_score",
        "curiosity_gap_score",
        "visual_pacing_score",
        "midpoint_reset_score",
        "cta_strength_score",
        "average_core_score",
        "dead_air_risk",
        "genericness_risk",
        "recommended_fixes",
        "generated_pending_review",
        "low",
        "medium",
        "high",
        "visual pacing risk",
        "hook and topic specificity risk",
    ]:
        assert term in content


def test_p25_retention_score_helper_generates_review_required_report_with_fixes() -> None:
    report = build_retention_score_report(
        package_id="pkg-weak-retention",
        content_type="short",
        topic="Neymar 2014 World Cup injury and comeback pressure",
        hook_text="Football story",
        cta_text="What do you think",
        subject="Neymar",
        has_midpoint_reset=False,
        has_visual_concepts=False,
    )

    assert REQUIRED_FIELDS <= set(report)
    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["package_id"] == "pkg-weak-retention"
    assert report["status"] == "generated_pending_review"
    assert report["approval_state"] == "not_approved"
    assert report["planned_epic"] == "P25"

    for score_field in [
        "hook_score",
        "first_1s_thumb_stop_score",
        "first_3s_clarity_score",
        "first_8s_retention_lock_score",
        "curiosity_gap_score",
        "visual_pacing_score",
        "midpoint_reset_score",
        "cta_strength_score",
    ]:
        assert 0 <= report[score_field] <= 10

    assert report["dead_air_risk"] in RISK_LABELS
    assert report["genericness_risk"] in RISK_LABELS
    assert "Open with a more specific football moment, player, or consequence." in report["recommended_fixes"]
    assert "Add a stronger first-frame visual interruption or high-contrast caption." in report["recommended_fixes"]
    assert "Add a midpoint reset such as a stat card, comparison, timeline jump, or 'but then' turn." in report["recommended_fixes"]
    assert "Does not approve publishing, monetization, rights, or editorial status." in report["notes"]


def test_p25_retention_score_helper_supports_strong_inputs_and_rejects_invalid_inputs() -> None:
    report = build_retention_score_report(
        package_id="pkg-strong-retention",
        content_type="explainer",
        topic="Neymar 2014 World Cup injury and comeback pressure",
        hook_text="What changed Neymar's World Cup forever?",
        cta_text="Was Neymar robbed of the legacy people expected?",
        subject="Neymar",
        has_midpoint_reset=True,
        has_visual_concepts=True,
    )

    assert report["content_type"] == "explainer"
    assert report["hook_score"] >= 8
    assert report["first_1s_thumb_stop_score"] >= 8
    assert report["midpoint_reset_score"] == 8
    assert report["dead_air_risk"] == "low"
    assert report["genericness_risk"] == "low"

    with pytest.raises(ValueError):
        build_retention_score_report(
            package_id="pkg-invalid",
            content_type="podcast",  # type: ignore[arg-type]
            topic="Neymar",
            hook_text="What changed Neymar?",
            cta_text="Was Neymar robbed?",
        )

    with pytest.raises(ValueError):
        build_retention_score_report(
            package_id="pkg-empty",
            content_type="short",
            topic="   ",
            hook_text="What changed Neymar?",
            cta_text="Was Neymar robbed?",
        )


def test_p25_retention_score_package_integration_and_writer_are_deterministic(tmp_path: Path) -> None:
    package = {
        "package_id": "pkg-integration",
        "retention": {
            "retention_score_path": None,
            "hook_score": None,
            "status": "pending_p25",
            "planned_epic": "P25",
        },
        "rights_and_monetization": {
            "publish_allowed": False,
        },
        "editorial_review": {
            "approval_state": "not_approved",
        },
    }
    report = build_retention_score_report(
        package_id="pkg-integration",
        content_type="short",
        topic="Neymar 2014 World Cup injury and comeback pressure",
        hook_text="What changed Neymar's World Cup forever?",
        cta_text="Was Neymar robbed of the legacy people expected?",
        subject="Neymar",
        has_midpoint_reset=True,
        has_visual_concepts=True,
    )

    updated = apply_retention_score_to_package(package, report_path="production/retention_score.json", report=report)
    assert updated is not package
    assert updated["retention"]["retention_score_path"] == "production/retention_score.json"
    assert updated["retention"]["hook_score"] == report["hook_score"]
    assert updated["retention"]["first_three_seconds_score"] == report["first_3s_clarity_score"]
    assert updated["retention"]["midpoint_reset_score"] == report["midpoint_reset_score"]
    assert updated["retention"]["cta_strength_score"] == report["cta_strength_score"]
    assert updated["retention"]["status"] == "generated_pending_review"
    assert updated["rights_and_monetization"]["publish_allowed"] is False
    assert updated["editorial_review"]["approval_state"] == "not_approved"

    output_path = write_retention_score_report(tmp_path / "retention_score.json", report)
    assert output_path == tmp_path / "retention_score.json"
    reloaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert reloaded == report


def test_p25_retention_score_example_contains_required_report_fields() -> None:
    report = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert REQUIRED_FIELDS <= set(report)
    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["package_id"] == "pkg-retention-example"
    assert report["content_type"] == "short"
    assert report["source_topic"] == "Neymar 2014 World Cup injury and comeback pressure"
    assert report["dead_air_risk"] in RISK_LABELS
    assert report["genericness_risk"] in RISK_LABELS
    assert report["recommended_fixes"]
    assert report["status"] == "generated_pending_review"
    assert report["approval_state"] == "not_approved"
    assert report["planned_epic"] == "P25"


def test_p25_retention_report_stop_conditions_guardrails_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "scores are described as real YouTube Analytics data",
        "scores are described as A/B test results",
        "a score automatically approves content",
        "a score automatically approves monetization",
        "a score automatically clears rights",
        "a score automatically approves editorial status",
        "`publish_allowed` is changed to `true`",
        "upload or publishing is introduced",
        "workflow gate bypass is requested",
        "No YouTube Analytics ingestion.",
        "No automated A/B testing.",
        "No automatic retention approval.",
        "No automatic publishing approval.",
        "No automatic monetization approval.",
        "No automatic rights clearance.",
        "No automatic editorial approval.",
        "No automatic upload.",
        "No automatic publishing.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p25_step_*.py" in harness
