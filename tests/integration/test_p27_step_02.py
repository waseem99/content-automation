from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.youtube_shorts_export import (
    YOUTUBE_SHORTS_EXPORT_DIRECTORY,
    YOUTUBE_SHORTS_PLATFORM,
    YOUTUBE_SHORTS_REQUIRED_FILES,
    build_youtube_shorts_export_pack,
)


pytestmark = pytest.mark.integration

DOC = Path("docs/operations/p27-step-02.md")
EXAMPLE = Path("docs/operations/p27-youtube-shorts-export-example.json")

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


def test_p27_youtube_shorts_doc_references_scope_inputs_and_outputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #329. Closes #351 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-readiness-report.md",
        "docs/operations/p27-step-01.md",
        "docs/operations/p27-export-directory-example.json",
        "src/title_options.py",
        "src/visual_concepts.py",
        "src/cta_library.py",
        "src/youtube_shorts_export.py",
        "docs/operations/p27-youtube-shorts-export-example.json",
        "tests/integration/test_p27_step_02.py",
        "exports/youtube_shorts/",
        "video.mp4",
        "title.txt",
        "description.txt",
        "hashtags.txt",
        "pinned_comment.txt",
        "first_frame_notes.txt",
        "risk_note.txt",
        "rights_note.txt",
        "metadata.json",
        "review_status.json",
    ]:
        assert term in content


def test_p27_youtube_shorts_doc_preserves_p25_p26_and_p29_review_rules() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "build_title_options(...)[0][\"title_text\"]",
        "build_cta_options(...)[0][\"cta_text\"]",
        "build_visual_concepts(... )[\"first_frame_options\"][0]",
        "selected P25 `title_option_id`, `first_frame_concept_id`, and `cta_id`",
        "`publish_allowed: false`",
        "`review_required: true`",
        "P26 monetization and rights review required",
        "P29 editorial approval required",
        "visible blocking reasons",
        "visible required actions",
        "no automatic rights clearance",
        "no automatic monetization approval",
        "no automatic editorial approval",
        "blocked_until_review",
        "This export pack is not an upload instruction, rights clearance, monetization approval, or publish approval.",
    ]:
        assert term in content


def test_p27_youtube_shorts_helper_builds_required_review_only_files() -> None:
    pack = build_youtube_shorts_export_pack(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
        source_package_path="docs/operations/p25-title-options-example.json",
        monetization_risk_report_path="docs/operations/p26-risk-report-medium-example.json",
        source_attribution_path="docs/operations/p26-source-attribution-example.json",
    )

    assert pack["schema_version"] == "p27.youtube_shorts_export_pack.v1"
    assert pack["platform"] == YOUTUBE_SHORTS_PLATFORM
    assert pack["export_directory"] == YOUTUBE_SHORTS_EXPORT_DIRECTORY
    assert pack["publish_allowed"] is False
    assert pack["review_required"] is True
    assert set(pack["required_files"]) == set(YOUTUBE_SHORTS_REQUIRED_FILES)
    assert set(pack["files"]) == set(YOUTUBE_SHORTS_REQUIRED_FILES)

    assert pack["files"]["video.mp4"]["status"] == "reference_only_not_committed"
    assert pack["files"]["title.txt"]["content"] == "The Neymar Question Fans Can't Ignore"
    assert "#footballshorts" in pack["files"]["hashtags.txt"]["content"]
    assert "Be honest: are fans too harsh on Neymar?" in pack["files"]["pinned_comment.txt"]["content"]
    assert "Selected concept: first_frame_01" in pack["files"]["first_frame_notes.txt"]["content"]
    assert "publish_allowed: false" in pack["files"]["risk_note.txt"]["content"]
    assert "P29 editorial status: missing" in pack["files"]["risk_note.txt"]["content"]
    assert "No automatic rights clearance is granted" in pack["files"]["rights_note.txt"]["content"]


def test_p27_youtube_shorts_helper_maps_metadata_review_status_and_p26_decision() -> None:
    decision = {
        "decision_state": "review_required",
        "blocking_reasons": ["Image attribution is unresolved.", "Human editorial approval is missing."],
        "required_actions": ["Resolve image attribution.", "Complete editorial review."],
    }
    pack = build_youtube_shorts_export_pack(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
        publish_block_decision=decision,
    )

    metadata = pack["metadata"]
    review_status = pack["review_status"]

    assert METADATA_FIELDS <= set(metadata)
    assert REVIEW_STATUS_FIELDS <= set(review_status)

    assert metadata["publish_allowed"] is False
    assert metadata["review_required"] is True
    assert metadata["platform"] == "youtube_shorts"
    assert metadata["created_by_step"] == "P27-02"
    assert metadata["planned_epic"] == "P27"
    assert metadata["p26_decision_state"] == "review_required"
    assert metadata["blocking_reasons"] == decision["blocking_reasons"]
    assert metadata["required_actions"] == decision["required_actions"]
    assert metadata["p25_packaging_sources"] == {
        "title_option_id": "title_01",
        "first_frame_concept_id": "first_frame_01",
        "cta_id": "cta_01",
    }

    assert review_status["export_status"] == "blocked_until_review"
    assert review_status["publish_allowed"] is False
    assert review_status["p26_review_status"] == "required"
    assert review_status["p29_editorial_status"] == "missing"
    assert review_status["rights_status"] == "review_required"
    assert review_status["monetization_status"] == "review_required"
    assert review_status["originality_status"] == "review_required"
    assert review_status["blocking_reasons"] == decision["blocking_reasons"]


def test_p27_youtube_shorts_example_contains_required_fixture_output() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert example["schema_version"] == "p27.youtube_shorts_export_pack.v1"
    assert example["package_id"] == "pkg-youtube-shorts-export-example"
    assert example["platform"] == "youtube_shorts"
    assert example["export_directory"] == "exports/youtube_shorts/"
    assert example["publish_allowed"] is False
    assert example["review_required"] is True
    assert set(example["required_files"]) == set(YOUTUBE_SHORTS_REQUIRED_FILES)
    assert set(example["files"]) == set(YOUTUBE_SHORTS_REQUIRED_FILES)

    metadata = example["metadata"]
    review_status = example["review_status"]
    assert METADATA_FIELDS <= set(metadata)
    assert REVIEW_STATUS_FIELDS <= set(review_status)
    assert metadata["publish_allowed"] is False
    assert review_status["publish_allowed"] is False
    assert review_status["p29_editorial_status"] == "missing"
    assert "title_option" in example["selected_p25_fields"]
    assert "first_frame_option" in example["selected_p25_fields"]
    assert "cta_option" in example["selected_p25_fields"]


def test_p27_youtube_shorts_helper_is_deterministic_and_rejects_invalid_inputs() -> None:
    first = build_youtube_shorts_export_pack("World Cup 2026 pressure index", subject="World Cup 2026")
    second = build_youtube_shorts_export_pack("World Cup 2026 pressure index", subject="World Cup 2026")
    assert first == second

    with pytest.raises(ValueError):
        build_youtube_shorts_export_pack("   ")

    with pytest.raises(ValueError):
        build_youtube_shorts_export_pack("World Cup", video_asset_path="   ")


def test_p27_youtube_shorts_stop_conditions_and_guardrails_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "the export pack is treated as upload approval",
        "`publish_allowed` defaults to `true`",
        "P26 publish-block rules are ignored",
        "P29 editorial approval is bypassed",
        "YouTube credentials are requested or stored",
        "YouTube API upload is introduced",
        "external rendered videos are committed",
        "secret values are committed",
        "workflow gate bypass is requested",
        "No YouTube API upload.",
        "No platform publishing.",
        "No YouTube Studio analytics integration.",
        "No platform credentials.",
        "No external video asset commits.",
        "No secret values.",
        "No automatic title approval.",
        "No automatic description approval.",
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
