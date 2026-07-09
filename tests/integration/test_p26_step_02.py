from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p26-step-02.md")
LOW = Path("docs/operations/p26-risk-report-low-example.json")
MEDIUM = Path("docs/operations/p26-risk-report-medium-example.json")
HIGH = Path("docs/operations/p26-risk-report-high-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "report_id",
    "package_id",
    "content_type",
    "overall_risk_level",
    "publish_allowed",
    "review_required",
    "risk_categories",
    "asset_risks",
    "blocking_reasons",
    "required_actions",
    "evidence_allowed",
    "evidence_blocked",
    "content_package_updates",
    "review_state",
    "reviewer_role",
    "notes",
}

REQUIRED_CATEGORIES = {
    "reused_content_risk",
    "copyright_risk",
    "image_license_risk",
    "music_license_risk",
    "ai_template_risk",
    "factual_risk",
    "originality_risk",
    "platform_reuse_risk",
    "brand_safety_risk",
}

REQUIRED_ASSET_FIELDS = {
    "asset_id",
    "asset_role",
    "asset_path",
    "default_risk_level",
    "current_risk_level",
    "review_required",
    "publish_blocking",
    "blocking_reasons",
    "required_actions",
    "evidence_allowed",
    "evidence_blocked",
    "notes",
}

ALLOWED_RISK_LABELS = {"low", "medium", "high", "blocked_until_review", "not_applicable"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p26_monetization_risk_schema_references_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #328. Closes #345 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-step-01.md",
        "src/content_package.py",
        "docs/operations/p26-risk-report-low-example.json",
        "docs/operations/p26-risk-report-medium-example.json",
        "docs/operations/p26-risk-report-high-example.json",
        "tests/integration/test_p26_step_02.py",
        "This `monetization_risk_report.json` schema is documentation and contract focused.",
        "provide legal advice",
        "clear copyrights",
        "predict Content ID claims",
        "predict copyright strikes",
        "verify licenses automatically",
        "enforce platform APIs",
        "approve YouTube monetization",
        "approve platform publishing",
        "upload to any platform",
        "publish content",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p26_monetization_risk_schema_documents_required_fields_categories_and_labels() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "schema_version",
        "p26.monetization_risk_report.v1",
        "report_id",
        "package_id",
        "content_type",
        "overall_risk_level",
        "publish_allowed",
        "review_required",
        "risk_categories",
        "asset_risks",
        "blocking_reasons",
        "required_actions",
        "evidence_allowed",
        "evidence_blocked",
        "content_package_updates",
        "review_state",
        "reviewer_role",
        "reused_content_risk",
        "copyright_risk",
        "image_license_risk",
        "music_license_risk",
        "ai_template_risk",
        "factual_risk",
        "originality_risk",
        "platform_reuse_risk",
        "brand_safety_risk",
        "low",
        "medium",
        "high",
        "blocked_until_review",
        "not_applicable",
    ]:
        assert term in content


def test_p26_monetization_risk_examples_have_required_shape() -> None:
    for path in [LOW, MEDIUM, HIGH]:
        report = _load(path)
        assert REQUIRED_TOP_LEVEL_FIELDS <= set(report)
        assert report["schema_version"] == "p26.monetization_risk_report.v1"
        assert report["publish_allowed"] is False
        assert report["review_required"] is True
        assert report["overall_risk_level"] in ALLOWED_RISK_LABELS
        assert REQUIRED_CATEGORIES <= set(report["risk_categories"])
        for category in REQUIRED_CATEGORIES:
            category_report = report["risk_categories"][category]
            assert category_report["risk_level"] in ALLOWED_RISK_LABELS
            assert "review_required" in category_report
            assert "publish_blocking" in category_report
            assert "reason" in category_report
            assert "required_actions" in category_report
        for asset in report["asset_risks"]:
            assert REQUIRED_ASSET_FIELDS <= set(asset)
            assert asset["default_risk_level"] in ALLOWED_RISK_LABELS
            assert asset["current_risk_level"] in ALLOWED_RISK_LABELS
        updates = report["content_package_updates"]
        for term in [
            "monetization_risk_report_path",
            "publish_allowed",
            "review_required",
            "rights_clearance_status",
            "source_attribution_status",
            "music_license_status",
            "originality_status",
            "blocking_reasons",
            "required_actions",
            "status",
            "planned_epic",
        ]:
            assert term in updates
        assert updates["publish_allowed"] is False
        assert updates["planned_epic"] == "P26"


def test_p26_monetization_risk_examples_cover_low_medium_and_high_states() -> None:
    low = _load(LOW)
    medium = _load(MEDIUM)
    high = _load(HIGH)

    assert low["overall_risk_level"] == "low"
    assert low["review_state"] == "generated_pending_review"
    assert "Low risk is not publish approval." in low["notes"]

    assert medium["overall_risk_level"] == "medium"
    assert medium["risk_categories"]["image_license_risk"]["publish_blocking"] is True
    assert "image license review pending" in medium["blocking_reasons"]

    assert high["overall_risk_level"] == "high"
    assert high["risk_categories"]["copyright_risk"]["risk_level"] == "blocked_until_review"
    assert high["content_package_updates"]["status"] == "blocked_until_review"
    assert "broadcast footage review pending" in high["blocking_reasons"]


def test_p26_monetization_risk_schema_documents_blocking_rules_and_package_linkage() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "any category has `publish_blocking: true`",
        "any asset has `publish_blocking: true`",
        "broadcast footage is unreviewed",
        "extracted clips are unreviewed",
        "music license is unverified",
        "web image license or attribution is unverified",
        "AI image provenance or likeness risk is unreviewed",
        "factual claims or stats are unsourced",
        "originality assessment is missing",
        "editorial approval is missing",
        "source evidence is treated as rights clearance",
        "platform export is requested before risk review",
        "`monetization_risk_report_path`",
        "`rights_clearance_status`",
        "`source_attribution_status`",
        "`music_license_status`",
        "`originality_status`",
        "This linkage does not approve the package or make it publish-ready.",
    ]:
        assert term in content


def test_p26_monetization_risk_stop_conditions_guardrails_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "`publish_allowed` defaults to `true`",
        "a low-risk report is treated as publish approval",
        "broadcast footage is treated as rights-cleared by default",
        "unverified music is treated as safe",
        "web image filtering is treated as legal clearance",
        "`image_sources.json` is treated as copyright clearance",
        "platform upload is introduced",
        "legal clearance is implied",
        "monetization approval is implied",
        "workflow gate bypass is requested",
        "No automated legal clearance.",
        "No copyright claim prediction.",
        "No Content ID prediction.",
        "No automatic license verification.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No automatic publishing approval.",
        "No automatic upload.",
        "No automatic publishing.",
        "No platform API enforcement.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external package exports.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p26_step_*.py" in harness
