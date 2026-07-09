from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p27-step-01.md")
EXAMPLE = Path("docs/operations/p27-export-directory-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

PLATFORMS = {
    "youtube_shorts",
    "youtube_longform",
    "tiktok",
    "instagram_reels",
    "facebook_reels",
    "x_twitter",
}

DIRECTORIES = {
    "exports/youtube_shorts/",
    "exports/youtube_longform/",
    "exports/tiktok/",
    "exports/instagram_reels/",
    "exports/facebook_reels/",
    "exports/x_twitter/",
}

METADATA_FIELDS = {
    "schema_version",
    "package_id",
    "platform",
    "export_directory",
    "content_type",
    "video_asset_path",
    "copy_asset_paths",
    "rights_note_path",
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
}

REVIEW_FIELDS = {
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


def test_p27_export_directory_contract_references_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #329. Closes #350 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-readiness-report.md",
        "docs/operations/p24-step-02.md",
        "docs/operations/p26-step-05.md",
        "src/content_package.py",
        "docs/operations/p27-export-directory-example.json",
        "tests/integration/test_p27_step_01.py",
        "This step is documentation and contract focused.",
        "generate export packs",
        "render new videos",
        "upload to platforms",
        "publish content",
        "approve monetization",
        "approve rights",
        "approve editorial status",
        "bypass P26 publish-block rules",
        "bypass P29 editorial approval",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p27_export_directory_contract_documents_required_directories_and_files() -> None:
    content = DOC.read_text(encoding="utf-8")
    assert "exports/" in content
    for directory in DIRECTORIES:
        assert directory in content

    for term in [
        "video.mp4",
        "metadata.json",
        "caption.txt",
        "hashtags.txt",
        "rights_note.txt",
        "review_status.json",
        "title.txt",
        "description.txt",
        "pinned_comment.txt",
        "thumbnail_brief.md",
        "chapters.txt",
        "source_list.txt",
        "music_rights_note.txt",
        "cover_note.txt",
        "cover_frame_note.txt",
        "collaborator_tags.txt",
        "monetization_note.txt",
        "post_copy.txt",
        "thread_outline.txt",
    ]:
        assert term in content


def test_p27_export_directory_contract_documents_metadata_review_and_platform_rules() -> None:
    content = DOC.read_text(encoding="utf-8")
    for field in METADATA_FIELDS:
        assert f"`{field}`" in content
    for field in REVIEW_FIELDS:
        assert f"`{field}`" in content
    for platform in PLATFORMS:
        assert f"`{platform}`" in content

    for term in [
        "contract_only",
        "not_started",
        "generated_pending_review",
        "blocked_until_review",
        "export_candidate_after_review",
        "`export_candidate_after_review` must not imply publish approval.",
        "Do not use inconsistent names",
        "youtube-long-form",
        "youtube_long_form",
        "twitter",
        "ig_reels",
        "fb_reels",
    ]:
        assert term in content


def test_p27_export_directory_contract_documents_package_linkage_p26_safety_and_downstream_mapping() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "the P24 `content_package.json`",
        "the P25 packaging fields",
        "the P25 retention fields",
        "the P26 `monetization_risk_report.json`",
        "the P26 source attribution records",
        "the P26 publish-block decision",
        "the future P29 editorial review status",
        "`publish_allowed: false`",
        "`review_required: true`",
        "P26 rights and monetization review required",
        "P29 editorial review required",
        "export files are not upload instructions",
        "export files are not publish approval",
        "P27-02 should generate the YouTube Shorts export pack.",
        "P27-03 should generate TikTok, Instagram Reels, and Facebook Reels export packs.",
        "P27-04 should generate X/Twitter caption and thread export pack.",
        "P27-05 should validate cross-platform export readiness.",
        "P27-06 should close P27 with readiness evidence.",
    ]:
        assert term in content


def test_p27_export_directory_example_has_all_platforms_and_review_defaults() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert example["schema_version"] == "p27.export_directory_contract.v1"
    assert example["package_id"] == "pkg-export-directory-example"
    assert example["publish_allowed"] is False
    assert example["review_required"] is True
    assert example["root_directory"] == "exports/"

    platforms = example["platforms"]
    assert {platform["platform"] for platform in platforms} == PLATFORMS
    assert {platform["export_directory"] for platform in platforms} == DIRECTORIES

    for platform in platforms:
        assert platform["publish_allowed"] is False
        assert platform["review_required"] is True
        assert platform["created_by_step"] == "P27-01"
        assert platform["planned_epic"] == "P27"
        assert set(platform["metadata_required_fields"]) == METADATA_FIELDS
        assert set(platform["review_status_required_fields"]) == REVIEW_FIELDS
        assert "metadata.json" in platform["required_files"]
        assert "review_status.json" in platform["required_files"]
        assert platform["blocking_reasons"]
        assert platform["required_actions"]


def test_p27_export_directory_example_platform_specific_files_are_present() -> None:
    platforms = {platform["platform"]: platform for platform in json.loads(EXAMPLE.read_text(encoding="utf-8"))["platforms"]}
    assert {"title.txt", "description.txt", "pinned_comment.txt"} <= set(platforms["youtube_shorts"]["required_files"])
    assert {"thumbnail_brief.md", "chapters.txt", "source_list.txt"} <= set(platforms["youtube_longform"]["required_files"])
    assert {"music_rights_note.txt", "cover_note.txt"} <= set(platforms["tiktok"]["required_files"])
    assert {"cover_frame_note.txt", "collaborator_tags.txt"} <= set(platforms["instagram_reels"]["required_files"])
    assert {"monetization_note.txt", "rights_note.txt"} <= set(platforms["facebook_reels"]["required_files"])
    assert {"post_copy.txt", "thread_outline.txt"} <= set(platforms["x_twitter"]["required_files"])


def test_p27_export_directory_stop_conditions_guardrails_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "an export directory is treated as upload approval",
        "`publish_allowed` defaults to `true`",
        "P26 publish-block rules are ignored",
        "P29 editorial approval is bypassed",
        "platform credentials are requested or stored",
        "platform APIs are introduced",
        "external exports are committed",
        "secret values are committed",
        "workflow gate bypass is requested",
        "No platform upload.",
        "No platform publishing.",
        "No platform API integration.",
        "No platform credentials.",
        "No external package exports.",
        "No secret values.",
        "No automatic publish approval.",
        "No automatic monetization approval.",
        "No automatic rights clearance.",
        "No automatic editorial approval.",
        "No bypass of P26 publish-block rules.",
        "No bypass of P29 editorial governance.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p27_step_*.py" in harness
