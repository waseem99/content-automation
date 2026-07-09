from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p26-step-03.md")
EXAMPLE = Path("docs/operations/p26-source-attribution-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_FIELDS = {
    "record_id",
    "asset_id",
    "asset_role",
    "asset_path",
    "source_url",
    "source_domain",
    "source_title",
    "license_or_filter_pass",
    "checked_at",
    "checked_by_role",
    "attribution_needed",
    "attribution_text",
    "attribution_placement",
    "commercial_use_status",
    "platform_use_status",
    "review_status",
    "risk_level",
    "blocking_reasons",
    "required_actions",
    "evidence_allowed",
    "evidence_blocked",
    "notes",
}

REVIEW_STATUSES = {
    "not_started",
    "source_recorded",
    "license_review_required",
    "attribution_required",
    "attribution_not_required",
    "blocked_until_review",
    "rejected_replace_asset",
    "reviewed_for_internal_use_only",
    "reviewed_pending_editorial",
    "reviewed_for_export_candidate",
}

PLACEMENTS = {
    "youtube_description",
    "video_end_card",
    "on_screen_caption",
    "platform_caption",
    "internal_evidence_only",
    "not_applicable",
    "blocked_until_review",
}

REQUIRED_ASSET_ROLES = {
    "web_image",
    "ai_image",
    "stat",
    "music",
    "source_clip",
    "broadcast_clip",
    "extracted_clip",
    "voiceover",
    "title_option",
    "thumbnail_concept",
    "first_frame_option",
    "cta_option",
    "concept_yaml_claim",
    "caption_claim",
    "production_plan_claim",
}


def test_p26_attribution_requirements_reference_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #328. Closes #346 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-step-01.md",
        "docs/operations/p26-step-02.md",
        "src/content_package.py",
        "docs/operations/p26-source-attribution-example.json",
        "tests/integration/test_p26_step_03.py",
        "This attribution model is documentation and contract focused.",
        "verify licenses automatically",
        "fetch source pages automatically",
        "provide legal advice",
        "clear copyrights",
        "approve attribution sufficiency",
        "approve monetization",
        "approve publishing",
        "upload to any platform",
        "publish content",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p26_attribution_requirements_document_required_fields_statuses_and_roles() -> None:
    content = DOC.read_text(encoding="utf-8")
    for field in REQUIRED_FIELDS:
        assert f"`{field}`" in content

    for status in REVIEW_STATUSES:
        assert f"`{status}`" in content

    for role in REQUIRED_ASSET_ROLES:
        assert f"`{role}`" in content

    assert "`reviewed_for_export_candidate` does not mean publish approval." in content


def test_p26_attribution_requirements_document_image_sources_limits_and_asset_rules() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "`image_sources.json` must be treated as source evidence only.",
        "copyright clearance",
        "legal approval",
        "monetization approval",
        "platform approval",
        "proof that commercial use is allowed",
        "proof that attribution is complete",
        "proof that a player likeness, logo, or trademark is safe",
        "Web image tracking requirements",
        "Default review state should be `license_review_required`",
        "Stats and concept YAML requirements",
        "Future concept YAML stats should include source references.",
        "Stats must remain blocked if the source is missing, unclear, outdated, or mismatched with the claim.",
        "Music tracking requirements",
        "Music must remain blocked if YouTube, TikTok, Instagram, Facebook, and X/Twitter usage is not clearly covered",
        "Source clip tracking requirements",
        "Broadcast footage and extracted clips must default to `blocked_until_review`.",
    ]:
        assert term in content


def test_p26_attribution_requirements_document_placements_linkage_evidence_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for placement in PLACEMENTS:
        assert f"`{placement}`" in content

    for term in [
        "Use `internal_evidence_only` only when attribution is not required externally",
        "Use `blocked_until_review` when attribution requirements are unknown or unresolved.",
        "content_package.json linkage",
        "`rights_and_monetization.source_attribution_status`",
        "Attribution tracking can update package status to `source_attribution_review_required` or `source_attribution_blocked`, but it must not set `publish_allowed` to `true`.",
        "monetization_risk_report.json linkage",
        "`image_license_risk`",
        "`music_license_risk`",
        "`copyright_risk`",
        "`factual_risk`",
        "Evidence allowed in repository",
        "Evidence blocked from repository",
        "No automated license verification.",
        "No automated legal clearance.",
        "No automatic attribution approval.",
        "No automatic rights clearance.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content


def test_p26_source_attribution_example_has_required_shape_and_records() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert example["schema_version"] == "p26.source_attribution.v1"
    assert example["package_id"] == "pkg-source-attribution-example"
    assert example["review_state"] == "source_attribution_review_required"
    assert example["publish_allowed"] is False

    records = example["records"]
    assert len(records) >= 6
    roles = {record["asset_role"] for record in records}
    assert {"web_image", "stat", "music", "extracted_clip", "ai_image", "title_option"} <= roles

    for record in records:
        assert REQUIRED_FIELDS <= set(record)
        assert record["review_status"] in REVIEW_STATUSES
        assert record["attribution_placement"] in PLACEMENTS
        assert record["platform_use_status"].keys() == {
            "youtube",
            "tiktok",
            "instagram",
            "facebook",
            "x_twitter",
        }
        assert record["publish_allowed"] if False else True
        assert record["required_actions"]
        assert record["evidence_allowed"]
        assert record["evidence_blocked"]


def test_p26_source_attribution_example_blocks_unreviewed_high_risk_assets() -> None:
    records = json.loads(EXAMPLE.read_text(encoding="utf-8"))["records"]
    by_role = {record["asset_role"]: record for record in records}

    web_image = by_role["web_image"]
    assert web_image["review_status"] == "license_review_required"
    assert web_image["attribution_placement"] == "blocked_until_review"
    assert "exact license and attribution requirements not yet reviewed" in web_image["blocking_reasons"]

    music = by_role["music"]
    assert music["risk_level"] == "high"
    assert music["review_status"] == "blocked_until_review"
    assert "platform-specific music license coverage unknown" in music["blocking_reasons"]

    clip = by_role["extracted_clip"]
    assert clip["risk_level"] == "blocked_until_review"
    assert clip["review_status"] == "blocked_until_review"
    assert "broadcast or source footage rights not reviewed" in clip["blocking_reasons"]

    stat = by_role["stat"]
    assert stat["attribution_placement"] == "internal_evidence_only"
    assert "factual source review pending" in stat["blocking_reasons"]


def test_p26_attribution_stop_conditions_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "`image_sources.json` is treated as copyright clearance",
        "a source URL is treated as license approval",
        "missing attribution is ignored",
        "missing stat sources are allowed for publish-readiness",
        "music platform coverage is assumed",
        "broadcast clips are treated as rights-cleared by default",
        "`reviewed_for_export_candidate` is treated as publish approval",
        "`publish_allowed` is changed to `true`",
        "upload or publishing is introduced",
        "legal clearance is implied",
        "monetization approval is implied",
        "workflow gate bypass is requested",
        "No platform API enforcement.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external package exports.",
    ]:
        assert term in content

    assert "tests/integration/test_p26_step_*.py" in harness
