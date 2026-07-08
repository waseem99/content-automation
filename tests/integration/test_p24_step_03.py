from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p24-step-03.md")
SHORT_EXAMPLE = Path("docs/operations/p24-content-package-short-example.json")
EXPLAINER_EXAMPLE = Path("docs/operations/p24-content-package-explainer-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "package_id",
    "run_identity",
    "content_type",
    "content_status",
    "source_assets",
    "generated_assets",
    "platform_suitability",
    "missing_assets",
    "packaging",
    "retention",
    "rights_and_monetization",
    "exports",
    "editorial_review",
    "next_actions",
    "guardrails",
}

REQUIRED_PLATFORMS = {
    "youtube_shorts",
    "youtube_long_form",
    "tiktok",
    "instagram_reels",
    "facebook_reels",
    "x_twitter",
}


def _load_example(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_p24_content_package_schema_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p24-step-01.md",
        "docs/operations/p24-step-02.md",
        "README.md",
        "src/producer.py",
        "src/explainer_producer.py",
        "src/domain/render_status.py",
        "docs/operations/p24-content-package-short-example.json",
        "docs/operations/p24-content-package-explainer-example.json",
        ".github/workflows/p1-acceptance-harness.yml",
        "Part of #326. Closes #334 after the PR merges.",
    ]:
        assert term in content


def test_p24_content_package_schema_is_contract_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This `content_package.json` schema is documentation and contract focused.",
        "generate final title options",
        "generate final first-frame options",
        "generate thumbnails",
        "score retention automatically",
        "score monetization risk automatically",
        "clear rights or copyright risk",
        "create platform export folders",
        "approve editorial status",
        "render videos",
        "upload to any platform",
        "publish content",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p24_content_package_examples_are_valid_json_and_include_required_top_level_fields() -> None:
    for path in [SHORT_EXAMPLE, EXPLAINER_EXAMPLE]:
        package = _load_example(path)
        assert package["schema_version"] == "p24.content_package.v1"
        assert REQUIRED_TOP_LEVEL_FIELDS <= set(package)
        assert package["content_status"] == "draft_contract_example"
        assert isinstance(package["source_assets"], list)
        assert isinstance(package["next_actions"], list)
        assert package["rights_and_monetization"]["publish_allowed"] is False
        assert package["editorial_review"]["approval_state"] == "not_approved"


def test_p24_content_package_examples_include_required_run_identity_generated_assets_and_platforms() -> None:
    for path in [SHORT_EXAMPLE, EXPLAINER_EXAMPLE]:
        package = _load_example(path)
        run_identity = package["run_identity"]
        for term in [
            "run_id",
            "run_folder",
            "campaign_id",
            "concept_id",
            "source_command",
            "created_at",
            "package_owner_role",
            "reviewer_role",
        ]:
            assert term in run_identity

        generated_assets = package["generated_assets"]
        for section in [
            "production_plans",
            "visuals",
            "audio",
            "captions",
            "rendered_outputs",
            "source_evidence",
            "checkpoints",
        ]:
            assert section in generated_assets

        assert REQUIRED_PLATFORMS <= set(package["platform_suitability"])
        for platform in REQUIRED_PLATFORMS:
            platform_package = package["platform_suitability"][platform]
            for term in [
                "status",
                "usable_current_assets",
                "missing_assets",
                "review_requirements",
                "publish_state",
            ]:
                assert term in platform_package
            assert platform_package["publish_state"] == "not_publish_ready"


def test_p24_content_package_examples_include_p25_p26_p27_p29_placeholders() -> None:
    for path in [SHORT_EXAMPLE, EXPLAINER_EXAMPLE]:
        package = _load_example(path)
        packaging = package["packaging"]
        for term in [
            "title_options",
            "first_frame_options",
            "thumbnail_concepts",
            "hook_notes",
            "cta_comment_trigger_options",
            "status",
            "planned_epic",
        ]:
            assert term in packaging
        assert packaging["status"] == "pending_p25"
        assert packaging["planned_epic"] == "P25"

        retention = package["retention"]
        for term in [
            "retention_score_path",
            "hook_score",
            "first_three_seconds_score",
            "midpoint_reset_score",
            "cta_strength_score",
            "dead_air_risk",
            "genericness_risk",
            "recommended_fixes",
            "status",
            "planned_epic",
        ]:
            assert term in retention
        assert retention["status"] == "pending_p25"

        rights = package["rights_and_monetization"]
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
            assert term in rights
        assert rights["publish_allowed"] is False
        assert rights["review_required"] is True
        assert rights["status"] == "pending_p26"

        exports = package["exports"]
        assert REQUIRED_PLATFORMS <= set(exports)
        assert exports["status"] == "pending_p27"
        assert exports["planned_epic"] == "P27"

        editorial = package["editorial_review"]
        assert editorial["status"] == "pending_p29"
        assert editorial["approval_state"] == "not_approved"


def test_p24_content_package_examples_block_preview_publication_and_keep_long_form_extensible() -> None:
    short_package = _load_example(SHORT_EXAMPLE)
    short_rendered_outputs = short_package["generated_assets"]["rendered_outputs"]
    preview_outputs = [output for output in short_rendered_outputs if output["render_mode"] == "preview"]
    assert preview_outputs
    assert all(output["publication_eligible"] is False for output in preview_outputs)

    for path in [SHORT_EXAMPLE, EXPLAINER_EXAMPLE]:
        package = _load_example(path)
        assert "youtube_long_form" in package["platform_suitability"]
        assert "youtube_long_form" in package["exports"]
        assert "long_form" in DOC.read_text(encoding="utf-8")
        assert "16:9" in DOC.read_text(encoding="utf-8")
        assert "chapter" in DOC.read_text(encoding="utf-8")
        assert "sponsor slot markers" in DOC.read_text(encoding="utf-8")


def test_p24_content_package_schema_documents_missing_assets_stop_conditions_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "title_options",
        "first_frame_options",
        "thumbnail_concepts",
        "upload_description",
        "hashtags",
        "pinned_comment",
        "retention_score",
        "hook_score",
        "cta_comment_trigger_options",
        "monetization_risk_report",
        "rights_clearance_status",
        "originality_assessment",
        "source_attribution_checklist",
        "music_license_note",
        "platform_export_folders",
        "human_editorial_review_status",
        "publish_readiness_manifest",
        "`publish_allowed` defaults to `true`",
        "`preview_video.mp4` is marked `publication_eligible: true`",
        "`image_sources.json` is treated as copyright clearance",
        "broadcast footage is treated as rights-cleared by default",
        "editorial approval is implied before P29",
        "monetization approval is implied before P26",
        "direct platform upload is added",
        "No automatic approval.",
        "No automatic release.",
        "No automatic rendering.",
        "No automatic publishing.",
        "No automatic upload.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No automatic legal approval.",
        "No automatic platform export.",
        "No automatic editorial approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external package exports.",
    ]:
        assert term in content

    assert "tests/integration/test_p24_step_*.py" in harness
