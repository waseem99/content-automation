from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.short_form_exports import (
    SHORT_FORM_PLATFORMS,
    SHORT_FORM_REQUIRED_FILES,
    build_short_form_export_pack,
    build_short_form_export_packs,
)


pytestmark = pytest.mark.integration

DOC = Path("docs/operations/p27-step-03.md")
EXAMPLE = Path("docs/operations/p27-short-form-export-example.json")

METADATA_FIELDS = {
    "schema_version",
    "package_id",
    "platform",
    "export_directory",
    "content_type",
    "video_asset_path",
    "copy_asset_paths",
    "review_status_path",
    "source_package_path",
    "monetization_risk_report_path",
    "source_attribution_path",
    "publish_allowed",
    "review_required",
    "blocking_reasons",
    "required_actions",
    "created_by_step",
    "planned_epic",
    "caption_style",
    "p25_packaging_sources",
    "p26_decision_state",
}

REVIEW_STATUS_FIELDS = {
    "platform",
    "package_id",
    "export_status",
    "publish_allowed",
    "p26_review_status",
    "p29_editorial_status",
    "rights_status",
    "monetization_status",
    "source_attribution_status",
    "music_license_status",
    "originality_status",
    "blocking_reasons",
    "required_actions",
    "reviewer_role",
    "notes",
}


def test_p27_short_form_doc_references_scope_inputs_and_outputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #329. Closes #352 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-readiness-report.md",
        "docs/operations/p27-step-01.md",
        "docs/operations/p27-step-02.md",
        "src/cta_library.py",
        "src/visual_concepts.py",
        "src/short_form_exports.py",
        "docs/operations/p27-short-form-export-example.json",
        "tests/integration/test_p27_step_03.py",
        "exports/tiktok/",
        "exports/instagram_reels/",
        "exports/facebook_reels/",
        "caption.txt",
        "hashtags.txt",
        "cover_notes.txt",
        "music_risk_note.txt",
        "publishing_note.txt",
    ]:
        assert term in content


def test_p27_short_form_doc_preserves_platform_differences_and_music_risk() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "fast_hook_direct_question",
        "polished_social_caption",
        "context_first_caption",
        "TikTok captions can use a faster direct hook",
        "Instagram Reels captions should be more polished",
        "Facebook Reels captions should provide slightly more context",
        "Music and sound rights must be reviewed separately for each platform.",
        "build_cta_options(...)[0][\"cta_text\"]",
        "build_visual_concepts(... )[\"first_frame_options\"][0]",
        "`publish_allowed: false`",
        "`review_required: true`",
        "platform-specific music rights review required",
        "no automatic music clearance",
        "no automatic rights clearance",
        "blocked_until_review",
    ]:
        assert term in content


def test_p27_short_form_helper_builds_all_platform_packs() -> None:
    packs = build_short_form_export_packs("Neymar 2014 World Cup injury and comeback pressure", subject="Neymar")

    assert set(packs) == set(SHORT_FORM_PLATFORMS)

    for platform, pack in packs.items():
        assert pack["schema_version"] == "p27.short_form_export_pack.v1"
        assert pack["platform"] == platform
        assert pack["publish_allowed"] is False
        assert pack["review_required"] is True
        assert set(pack["required_files"]) == set(SHORT_FORM_REQUIRED_FILES)
        assert set(pack["files"]) == set(SHORT_FORM_REQUIRED_FILES)

        assert pack["files"]["video.mp4"]["status"] == "reference_only_not_committed"
        assert "Be honest: are fans too harsh on Neymar?" in pack["files"]["caption.txt"]["content"]
        assert "#football" in pack["files"]["hashtags.txt"]["content"]
        assert "Selected first-frame concept: first_frame_01" in pack["files"]["cover_notes.txt"]["content"]
        assert "Do not assume one music license works across TikTok, Instagram Reels, and Facebook Reels." in pack["files"]["music_risk_note.txt"]["content"]
        assert "publish_allowed: false" in pack["files"]["publishing_note.txt"]["content"]


def test_p27_short_form_helper_maps_metadata_review_status_and_p26_decision() -> None:
    decision = {
        "decision_state": "review_required",
        "blocking_reasons": ["Music license is not verified.", "Human editorial approval is missing."],
        "required_actions": ["Verify platform-specific music license.", "Complete editorial review."],
    }
    pack = build_short_form_export_pack(
        "instagram_reels",
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
        publish_block_decision=decision,
    )

    metadata = pack["metadata"]
    review_status = pack["review_status"]

    assert METADATA_FIELDS <= set(metadata)
    assert REVIEW_STATUS_FIELDS <= set(review_status)
    assert metadata["platform"] == "instagram_reels"
    assert metadata["caption_style"] == "polished_social_caption"
    assert metadata["publish_allowed"] is False
    assert metadata["review_required"] is True
    assert metadata["created_by_step"] == "P27-03"
    assert metadata["planned_epic"] == "P27"
    assert metadata["p26_decision_state"] == "review_required"
    assert metadata["blocking_reasons"] == decision["blocking_reasons"]
    assert metadata["required_actions"] == decision["required_actions"]
    assert metadata["p25_packaging_sources"] == {
        "cta_id": "cta_01",
        "first_frame_concept_id": "first_frame_01",
    }

    assert review_status["export_status"] == "blocked_until_review"
    assert review_status["publish_allowed"] is False
    assert review_status["p26_review_status"] == "required"
    assert review_status["p29_editorial_status"] == "missing"
    assert review_status["music_license_status"] == "platform_specific_review_required"
    assert review_status["blocking_reasons"] == decision["blocking_reasons"]


def test_p27_short_form_platform_outputs_are_distinct() -> None:
    tiktok = build_short_form_export_pack("tiktok", "World Cup 2026 pressure index", subject="World Cup 2026")
    instagram = build_short_form_export_pack("instagram_reels", "World Cup 2026 pressure index", subject="World Cup 2026")
    facebook = build_short_form_export_pack("facebook_reels", "World Cup 2026 pressure index", subject="World Cup 2026")

    assert tiktok["export_directory"] == "exports/tiktok/"
    assert instagram["export_directory"] == "exports/instagram_reels/"
    assert facebook["export_directory"] == "exports/facebook_reels/"

    assert tiktok["metadata"]["caption_style"] == "fast_hook_direct_question"
    assert instagram["metadata"]["caption_style"] == "polished_social_caption"
    assert facebook["metadata"]["caption_style"] == "context_first_caption"

    assert "#footballtiktok" in tiktok["files"]["hashtags.txt"]["content"]
    assert "#reels" in instagram["files"]["hashtags.txt"]["content"]
    assert "#facebookreels" in facebook["files"]["hashtags.txt"]["content"]

    assert tiktok["files"]["caption.txt"]["content"] != instagram["files"]["caption.txt"]["content"]
    assert instagram["files"]["caption.txt"]["content"] != facebook["files"]["caption.txt"]["content"]


def test_p27_short_form_example_contains_required_fixture_output() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert example["schema_version"] == "p27.short_form_export_pack_collection.v1"
    assert set(example["platforms"]) == set(SHORT_FORM_PLATFORMS)

    for platform in SHORT_FORM_PLATFORMS:
        pack = example["packs"][platform]
        assert pack["platform"] == platform
        assert pack["publish_allowed"] is False
        assert pack["review_required"] is True
        assert set(pack["required_files"]) == set(SHORT_FORM_REQUIRED_FILES)
        assert set(pack["files"]) == set(SHORT_FORM_REQUIRED_FILES)
        assert METADATA_FIELDS <= set(pack["metadata"])
        assert REVIEW_STATUS_FIELDS <= set(pack["review_status"])
        assert pack["review_status"]["p29_editorial_status"] == "missing"
        assert "music_risk_note.txt" in pack["files"]


def test_p27_short_form_helper_is_deterministic_and_rejects_invalid_inputs() -> None:
    first = build_short_form_export_packs("World Cup 2026 pressure index", subject="World Cup 2026")
    second = build_short_form_export_packs("World Cup 2026 pressure index", subject="World Cup 2026")
    assert first == second

    with pytest.raises(ValueError):
        build_short_form_export_pack("youtube_shorts", "World Cup")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        build_short_form_export_pack("tiktok", "   ")


def test_p27_short_form_stop_conditions_and_guardrails_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "the export pack is treated as platform upload approval",
        "`publish_allowed` defaults to `true`",
        "P26 publish-block rules are ignored",
        "P29 editorial approval is bypassed",
        "TikTok or Meta credentials are requested or stored",
        "TikTok or Meta API upload is introduced",
        "music licensing automation is introduced",
        "one music license is assumed to work across all platforms",
        "external rendered videos are committed",
        "secret values are committed",
        "workflow gate bypass is requested",
        "No TikTok upload.",
        "No Meta upload.",
        "No platform API integration.",
        "No platform credentials.",
        "No music licensing automation.",
        "No assumption that one music license works across all platforms.",
        "No external video asset commits.",
        "No secret values.",
        "No automatic caption approval.",
        "No automatic cover approval.",
        "No automatic music clearance.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No automatic editorial approval.",
        "No bypass of P26 publish-block rules.",
        "No bypass of P29 editorial governance.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content
