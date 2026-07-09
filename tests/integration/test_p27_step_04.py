from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.x_twitter_export import (
    X_TWITTER_EXPORT_DIRECTORY,
    X_TWITTER_PLATFORM,
    X_TWITTER_REQUIRED_FILES,
    build_x_twitter_export_pack,
)


pytestmark = pytest.mark.integration

DOC = Path("docs/operations/p27-step-04.md")
EXAMPLE = Path("docs/operations/p27-x-twitter-export-example.json")

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
    "copy_constraints",
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
    "factual_status",
    "originality_status",
    "blocking_reasons",
    "required_actions",
    "reviewer_role",
    "notes",
}


def test_p27_x_twitter_doc_references_scope_inputs_and_outputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #329. Closes #353 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-readiness-report.md",
        "docs/operations/p27-step-01.md",
        "docs/operations/p27-step-02.md",
        "docs/operations/p27-step-03.md",
        "src/cta_library.py",
        "src/x_twitter_export.py",
        "docs/operations/p27-x-twitter-export-example.json",
        "tests/integration/test_p27_step_04.py",
        "exports/x_twitter/",
        "post.txt",
        "thread.txt",
        "hashtags.txt",
        "debate_prompt.txt",
        "risk_note.txt",
    ]:
        assert term in content


def test_p27_x_twitter_doc_preserves_copy_rules_and_review_safety() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "short",
        "specific",
        "debate-oriented",
        "The post must stay within the 280-character limit.",
        "Thread output is available for explainers",
        "build_cta_options(...)[0][\"cta_text\"]",
        "selected P25 `cta_id`",
        "`publish_allowed: false`",
        "`review_required: true`",
        "factual/stat review required",
        "no automatic rights clearance",
        "no automatic monetization approval",
        "no automatic editorial approval",
        "blocked_until_review",
    ]:
        assert term in content


def test_p27_x_twitter_helper_builds_required_review_only_files() -> None:
    pack = build_x_twitter_export_pack(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
        source_package_path="docs/operations/p25-title-options-example.json",
        monetization_risk_report_path="docs/operations/p26-risk-report-medium-example.json",
        source_attribution_path="docs/operations/p26-source-attribution-example.json",
    )

    assert pack["schema_version"] == "p27.x_twitter_export_pack.v1"
    assert pack["platform"] == X_TWITTER_PLATFORM
    assert pack["export_directory"] == X_TWITTER_EXPORT_DIRECTORY
    assert pack["publish_allowed"] is False
    assert pack["review_required"] is True
    assert set(pack["required_files"]) == set(X_TWITTER_REQUIRED_FILES)
    assert set(pack["files"]) == set(X_TWITTER_REQUIRED_FILES)

    assert pack["files"]["video.mp4"]["status"] == "reference_only_not_committed"
    assert len(pack["files"]["post.txt"]["content"]) <= 280
    assert "football debate" in pack["files"]["post.txt"]["content"]
    assert "1/ Short context:" in pack["files"]["thread.txt"]["content"]
    assert "#football" in pack["files"]["hashtags.txt"]["content"]
    assert "Be honest: are fans too harsh on Neymar?" in pack["files"]["debate_prompt.txt"]["content"]
    assert "publish_allowed: false" in pack["files"]["risk_note.txt"]["content"]
    assert "Stats, rights, and source claims are not automatically cleared." in pack["files"]["risk_note.txt"]["content"]


def test_p27_x_twitter_helper_supports_explainer_thread_summary() -> None:
    pack = build_x_twitter_export_pack(
        "World Cup 2026 pressure index",
        subject="World Cup 2026",
        content_type="explainer",
    )

    thread = pack["files"]["thread.txt"]["content"]
    assert pack["metadata"]["content_type"] == "explainer"
    assert "1/ World Cup 2026 pressure index" in thread
    assert "2/ The key angle is why World Cup 2026 still creates debate among fans." in thread
    assert "4/ Final question:" in thread


def test_p27_x_twitter_helper_maps_metadata_review_status_and_p26_decision() -> None:
    decision = {
        "decision_state": "review_required",
        "blocking_reasons": ["Missing stat source reference.", "Human editorial approval is missing."],
        "required_actions": ["Verify stat source.", "Complete editorial review."],
    }
    pack = build_x_twitter_export_pack(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
        publish_block_decision=decision,
    )

    metadata = pack["metadata"]
    review_status = pack["review_status"]

    assert METADATA_FIELDS <= set(metadata)
    assert REVIEW_STATUS_FIELDS <= set(review_status)

    assert metadata["platform"] == "x_twitter"
    assert metadata["created_by_step"] == "P27-04"
    assert metadata["planned_epic"] == "P27"
    assert metadata["publish_allowed"] is False
    assert metadata["review_required"] is True
    assert metadata["copy_constraints"]["post_max_chars"] == 280
    assert metadata["copy_constraints"]["style"] == "short_specific_debate_oriented"
    assert metadata["p25_packaging_sources"] == {"cta_id": "cta_01"}
    assert metadata["p26_decision_state"] == "review_required"
    assert metadata["blocking_reasons"] == decision["blocking_reasons"]
    assert metadata["required_actions"] == decision["required_actions"]

    assert review_status["export_status"] == "blocked_until_review"
    assert review_status["publish_allowed"] is False
    assert review_status["p26_review_status"] == "required"
    assert review_status["p29_editorial_status"] == "missing"
    assert review_status["factual_status"] == "review_required"
    assert review_status["blocking_reasons"] == decision["blocking_reasons"]


def test_p27_x_twitter_example_contains_required_fixture_output() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert example["schema_version"] == "p27.x_twitter_export_pack.v1"
    assert example["platform"] == "x_twitter"
    assert example["export_directory"] == "exports/x_twitter/"
    assert example["publish_allowed"] is False
    assert example["review_required"] is True
    assert set(example["required_files"]) == set(X_TWITTER_REQUIRED_FILES)
    assert set(example["files"]) == set(X_TWITTER_REQUIRED_FILES)

    metadata = example["metadata"]
    review_status = example["review_status"]
    assert METADATA_FIELDS <= set(metadata)
    assert REVIEW_STATUS_FIELDS <= set(review_status)
    assert metadata["publish_allowed"] is False
    assert review_status["publish_allowed"] is False
    assert review_status["p29_editorial_status"] == "missing"
    assert "post.txt" in example["files"]
    assert "thread.txt" in example["files"]
    assert "debate_prompt.txt" in example["files"]
    assert "risk_note.txt" in example["files"]


def test_p27_x_twitter_helper_is_deterministic_and_rejects_invalid_inputs() -> None:
    first = build_x_twitter_export_pack("World Cup 2026 pressure index", subject="World Cup 2026")
    second = build_x_twitter_export_pack("World Cup 2026 pressure index", subject="World Cup 2026")
    assert first == second

    with pytest.raises(ValueError):
        build_x_twitter_export_pack("   ")

    with pytest.raises(ValueError):
        build_x_twitter_export_pack("World Cup", content_type="thread")  # type: ignore[arg-type]


def test_p27_x_twitter_stop_conditions_and_guardrails_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "the export pack is treated as post approval",
        "`publish_allowed` defaults to `true`",
        "P26 publish-block rules are ignored",
        "P29 editorial approval is bypassed",
        "X API credentials are requested or stored",
        "X API posting is introduced",
        "scraping replies or engagement data is introduced",
        "stats or factual claims are treated as verified without review",
        "external rendered videos are committed",
        "secret values are committed",
        "workflow gate bypass is requested",
        "No X API posting.",
        "No reply scraping.",
        "No engagement-data scraping.",
        "No platform credentials.",
        "No external video asset commits.",
        "No secret values.",
        "No automatic post approval.",
        "No automatic thread approval.",
        "No automatic factual/stat approval.",
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
