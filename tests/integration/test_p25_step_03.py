from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.visual_concepts import VISUAL_PATTERNS, build_visual_concepts


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p25-step-03.md")
EXAMPLE = Path("docs/operations/p25-visual-concepts-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_FIELDS = {
    "concept_id",
    "concept_type",
    "source_topic",
    "content_type",
    "platform_fit",
    "visual_pattern",
    "visual_layout",
    "suggested_text",
    "emotion",
    "focal_subject",
    "contrast_idea",
    "risk_notes",
    "approval_state",
}


def test_p25_visual_concepts_contract_references_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #327. Closes #340 after the PR merges.",
        "docs/operations/p24-step-03.md",
        "docs/operations/p24-step-05.md",
        "docs/operations/p25-step-01.md",
        "docs/operations/p25-step-02.md",
        "src/title_options.py",
        "src/visual_concepts.py",
        "docs/operations/p25-visual-concepts-example.json",
        "tests/integration/test_p25_step_03.py",
        "define first-frame concept schema",
        "define thumbnail concept schema",
        "generate first-frame options",
        "generate thumbnail concepts",
        "include visual layout guidance",
        "include suggested text",
        "include emotion",
        "include focal subject",
        "include contrast idea",
        "include risk notes",
        "does not render actual thumbnails",
        "does not generate images",
        "does not call image-generation APIs",
        "does not upload to YouTube",
        "does not publish content",
    ]:
        assert term in content


def test_p25_visual_concepts_schema_patterns_and_requirements_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "concept_id",
        "concept_type",
        "source_topic",
        "content_type",
        "platform_fit",
        "visual_pattern",
        "visual_layout",
        "suggested_text",
        "emotion",
        "focal_subject",
        "contrast_idea",
        "risk_notes",
        "approval_state",
        "first_frame",
        "thumbnail",
        "freeze_frame_punch_in",
        "split_screen_debate",
        "injury_goal_reaction_frame",
        "stat_card_frame",
        "legacy_vs_future_frame",
        "work with sound off",
        "support 16:9 long-form packaging",
        "create curiosity without misleading claims",
    ]:
        assert term in content


def test_p25_visual_concepts_helper_generates_review_required_options() -> None:
    topic = "Neymar 2014 World Cup injury and comeback pressure"
    concepts = build_visual_concepts(topic, subject="Neymar", content_type="short")

    assert set(concepts) == {"first_frame_options", "thumbnail_concepts"}
    assert len(concepts["first_frame_options"]) == 5
    assert len(concepts["thumbnail_concepts"]) == 5

    all_concepts = concepts["first_frame_options"] + concepts["thumbnail_concepts"]
    assert {concept["visual_pattern"] for concept in concepts["first_frame_options"]} == set(VISUAL_PATTERNS)
    assert {concept["visual_pattern"] for concept in concepts["thumbnail_concepts"]} == set(VISUAL_PATTERNS)

    for concept in all_concepts:
        assert REQUIRED_FIELDS <= set(concept)
        assert concept["source_topic"] == topic
        assert concept["content_type"] == "short"
        assert concept["focal_subject"] == "Neymar"
        assert concept["suggested_text"]
        assert concept["visual_layout"]
        assert concept["contrast_idea"]
        assert concept["approval_state"] == "not_approved"
        assert "Requires editorial review before use." in concept["risk_notes"]
        assert "Must not use unlicensed player, broadcast, logo, or match imagery without rights review." in concept["risk_notes"]

    assert all("youtube_shorts" in concept["platform_fit"] for concept in concepts["first_frame_options"])
    assert all("youtube_long_form" in concept["platform_fit"] for concept in concepts["thumbnail_concepts"])


def test_p25_visual_concepts_helper_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        build_visual_concepts("   ")

    with pytest.raises(ValueError):
        build_visual_concepts("Neymar", subject="   ")

    with pytest.raises(ValueError):
        build_visual_concepts("Neymar", content_type="podcast")  # type: ignore[arg-type]


def test_p25_visual_concepts_example_contains_first_frame_and_thumbnail_options() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    packaging = example["packaging"]
    first_frame_options = packaging["first_frame_options"]
    thumbnail_concepts = packaging["thumbnail_concepts"]

    assert example["schema_version"] == "p24.content_package.v1"
    assert example["source_topic"] == "Neymar 2014 World Cup injury and comeback pressure"
    assert len(first_frame_options) >= 3
    assert len(thumbnail_concepts) >= 3

    for concept in first_frame_options + thumbnail_concepts:
        assert REQUIRED_FIELDS <= set(concept)
        assert concept["source_topic"] == example["source_topic"]
        assert concept["suggested_text"]
        assert concept["risk_notes"]
        assert concept["approval_state"] == "not_approved"

    assert {"freeze_frame_punch_in", "split_screen_debate", "injury_goal_reaction_frame"} <= {
        concept["visual_pattern"] for concept in first_frame_options
    }
    assert {"freeze_frame_punch_in", "stat_card_frame", "legacy_vs_future_frame"} <= {
        concept["visual_pattern"] for concept in thumbnail_concepts
    }


def test_p25_visual_concepts_risk_rules_guardrails_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "misleading visual claims",
        "fake injuries or fake controversies",
        "unlicensed player images",
        "unlicensed broadcast stills",
        "unlicensed club or tournament logos",
        "implying rights clearance",
        "the visual concept matches the script or concept",
        "the suggested text matches the title and hook",
        "source imagery has rights review",
        "visual concepts are marked approved automatically",
        "thumbnails are rendered in this step",
        "first-frame images are rendered in this step",
        "image-generation APIs are called",
        "No misleading visual claims.",
        "No fake injuries.",
        "No fake scandals.",
        "No automatic visual approval.",
        "No automatic image generation.",
        "No thumbnail rendering in this step.",
        "No first-frame rendering in this step.",
        "No automatic upload.",
        "No automatic publishing.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No automatic editorial approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p25_step_*.py" in harness
