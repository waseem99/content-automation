from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.long_form_concept import (
    LONG_FORM_ASPECT_RATIO,
    LONG_FORM_CONTENT_TYPE,
    LONG_FORM_SCHEMA_VERSION,
    LONG_FORM_SECTION_TYPES,
    REQUIRED_CHAPTER_FIELDS,
    REQUIRED_LONG_FORM_FIELDS,
    build_long_form_concept,
    validate_long_form_concept,
)


pytestmark = pytest.mark.integration

DOC_PATH = Path("docs/operations/p28-step-01.md")
EXAMPLE_PATH = Path("docs/operations/p28-long-form-concept-example.json")


def test_p28_step_01_documentation_covers_issue_scope() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for term in [
        "Part of #330. Closes #356 after the PR merges.",
        "6–8 minute YouTube football videos",
        "16:9",
        "audience",
        "central_question",
        "source_requirements",
        "visual_style",
        "sponsor_slot_markers",
        "shorts_compatibility",
        "platform_packaging",
        "src/long_form_concept.py",
        "tests/integration/test_p28_step_01.py",
    ]:
        assert term in content


def test_p28_step_01_documentation_lists_section_types_and_guardrails() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for section_type in LONG_FORM_SECTION_TYPES:
        assert section_type in content

    for guardrail in [
        "render a long-form video",
        "introduce YouTube upload APIs",
        "connect YouTube Studio analytics",
        "treat this concept as editorial approval",
        "set `publish_allowed` to `true`",
        "skip rights review",
        "skip factual review",
        "skip P26 or P29 gates",
        "commit external video assets",
        "commit platform credentials or secrets",
        "bypass workflow gates",
    ]:
        assert guardrail in content


def test_build_long_form_concept_required_fields_and_defaults() -> None:
    concept = build_long_form_concept(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )

    assert set(REQUIRED_LONG_FORM_FIELDS) <= set(concept)
    assert concept["schema_version"] == LONG_FORM_SCHEMA_VERSION
    assert concept["content_type"] == LONG_FORM_CONTENT_TYPE
    assert concept["format"] == LONG_FORM_ASPECT_RATIO
    assert concept["subject"] == "Neymar"
    assert concept["target_duration_minutes"] == 7
    assert concept["target_duration_seconds"] == 420
    assert concept["publish_allowed"] is False
    assert concept["review_required"] is True


def test_long_form_concept_chapter_structure_and_source_requirements() -> None:
    concept = build_long_form_concept("Messi 2022 World Cup pressure", subject="Messi")

    assert [chapter["section_type"] for chapter in concept["chapters"]] == list(LONG_FORM_SECTION_TYPES)
    assert sum(chapter["target_duration_seconds"] for chapter in concept["chapters"]) == 420

    for chapter in concept["chapters"]:
        assert set(REQUIRED_CHAPTER_FIELDS) <= set(chapter)
        assert chapter["section_type"] in LONG_FORM_SECTION_TYPES
        assert isinstance(chapter["shorts_cutdown_candidate"], bool)

    source_requirements = concept["source_requirements"]
    assert source_requirements["minimum_sources"] >= 3
    assert source_requirements["rights_review_required"] is True
    assert source_requirements["factual_review_required"] is True
    assert source_requirements["source_attribution_required"] is True
    assert "unavailable" in source_requirements["unavailable_footage_policy"]


def test_long_form_concept_shorts_and_platform_packaging_compatibility() -> None:
    concept = build_long_form_concept("Arsenal invincibles legacy", subject="Arsenal")

    shorts = concept["shorts_compatibility"]
    assert shorts["compatible_with_shorts_cutdowns"] is True
    assert shorts["p27_platform_packaging_ready_after_review"] is True
    assert "cold_open" in shorts["recommended_cutdown_sections"]
    assert "turning_point" in shorts["recommended_cutdown_sections"]

    packaging = concept["platform_packaging"]
    assert packaging["youtube_long_form"]["direct_upload_out_of_scope"] is True
    assert packaging["youtube_long_form"]["chapters_required"] is True
    assert packaging["youtube_long_form"]["thumbnail_brief_required"] is True
    assert packaging["shorts_funnel"]["uses_p27_exports_after_review"] is True


def test_validate_long_form_concept_accepts_generated_concept() -> None:
    concept = build_long_form_concept(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )
    result = validate_long_form_concept(concept)

    assert result["schema_version"] == "p28.long_form_concept_validation.v1"
    assert result["is_valid"] is True
    assert result["publish_allowed"] is False
    assert result["review_required"] is True
    assert result["errors"] == []
    assert result["section_types_seen"] == list(LONG_FORM_SECTION_TYPES)
    assert result["target_duration_seconds"] == 420
    assert result["chapter_duration_seconds"] == 420


def test_validate_long_form_concept_catches_missing_required_fields() -> None:
    concept = build_long_form_concept("Neymar 2014 World Cup injury and comeback pressure", subject="Neymar")
    del concept["audience"]

    result = validate_long_form_concept(concept)

    assert result["is_valid"] is False
    assert "missing required long-form fields" in result["errors"]
    assert "audience must be non-empty text" in result["errors"]


def test_validate_long_form_concept_catches_invalid_chapter_sequence() -> None:
    concept = build_long_form_concept("Neymar 2014 World Cup injury and comeback pressure", subject="Neymar")
    concept["chapters"] = list(reversed(concept["chapters"]))

    result = validate_long_form_concept(concept)

    assert result["is_valid"] is False
    assert "chapter section sequence mismatch" in result["errors"]


def test_validate_long_form_concept_catches_publish_and_upload_regression() -> None:
    concept = build_long_form_concept("Neymar 2014 World Cup injury and comeback pressure", subject="Neymar")
    concept["publish_allowed"] = True
    concept["platform_packaging"]["youtube_long_form"]["direct_upload_out_of_scope"] = False

    result = validate_long_form_concept(concept)

    assert result["is_valid"] is False
    assert "publish_allowed must remain false" in result["errors"]
    assert "direct upload must remain out of scope" in result["errors"]


def test_validate_long_form_concept_catches_review_requirement_regression() -> None:
    concept = build_long_form_concept("Neymar 2014 World Cup injury and comeback pressure", subject="Neymar")
    concept["review_required"] = False
    concept["source_requirements"]["rights_review_required"] = False
    concept["source_requirements"]["factual_review_required"] = False

    result = validate_long_form_concept(concept)

    assert result["is_valid"] is False
    assert "review_required must remain true" in result["errors"]
    assert "rights review must be required" in result["errors"]
    assert "factual review must be required" in result["errors"]


def test_build_long_form_concept_validates_input_duration_and_text() -> None:
    with pytest.raises(ValueError):
        build_long_form_concept("   ")

    with pytest.raises(ValueError):
        build_long_form_concept("Neymar comeback", target_duration_minutes=5)

    with pytest.raises(ValueError):
        build_long_form_concept("Neymar comeback", target_duration_minutes=9)


def test_long_form_concept_example_is_valid_and_review_only() -> None:
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    result = validate_long_form_concept(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == LONG_FORM_SCHEMA_VERSION
    assert example["content_type"] == LONG_FORM_CONTENT_TYPE
    assert example["format"] == LONG_FORM_ASPECT_RATIO
    assert example["target_duration_minutes"] == 7
    assert example["publish_allowed"] is False
    assert example["review_required"] is True
    assert [chapter["section_type"] for chapter in example["chapters"]] == list(LONG_FORM_SECTION_TYPES)


def test_long_form_concept_output_is_deterministic() -> None:
    first = build_long_form_concept("Neymar 2014 World Cup injury and comeback pressure", subject="Neymar")
    second = build_long_form_concept("Neymar 2014 World Cup injury and comeback pressure", subject="Neymar")

    assert first == second
