from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.title_options import TITLE_STYLES, build_title_options


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p25-step-02.md")
EXAMPLE = Path("docs/operations/p25-title-options-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_FIELDS = {
    "option_id",
    "title_text",
    "title_style",
    "angle",
    "emotional_trigger",
    "platform_fit",
    "source_topic",
    "content_type",
    "risk_notes",
    "approval_state",
}


def test_p25_title_options_contract_references_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #327. Closes #339 after the PR merges.",
        "docs/operations/p24-step-03.md",
        "docs/operations/p24-step-05.md",
        "docs/operations/p25-step-01.md",
        "src/content_package.py",
        "src/title_options.py",
        "docs/operations/p25-title-options-example.json",
        "tests/integration/test_p25_step_02.py",
        "define a structured title option schema",
        "generate 10 title option stubs per topic",
        "avoid external API calls",
        "does not approve titles",
        "does not upload titles to YouTube",
        "does not run YouTube A/B tests",
        "does not generate thumbnails",
        "does not generate first-frame images",
        "does not publish content",
    ]:
        assert term in content


def test_p25_title_options_schema_and_styles_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "option_id",
        "title_text",
        "title_style",
        "angle",
        "emotional_trigger",
        "platform_fit",
        "source_topic",
        "content_type",
        "risk_notes",
        "approval_state",
        "curiosity",
        "debate",
        "nostalgia",
        "record_chase",
        "shock",
        "explainer",
        "legacy",
        "pressure",
        "versus",
        "prediction",
    ]:
        assert term in content


def test_p25_title_options_helper_generates_ten_review_required_options() -> None:
    topic = "Neymar 2014 World Cup injury and comeback pressure"
    options = build_title_options(topic, subject="Neymar", content_type="short")

    assert len(options) == 10
    assert {option["title_style"] for option in options} == set(TITLE_STYLES)

    for option in options:
        assert REQUIRED_FIELDS <= set(option)
        assert option["source_topic"] == topic
        assert option["content_type"] == "short"
        assert option["approval_state"] == "not_approved"
        assert "Neymar" in option["title_text"]
        assert "youtube_shorts" in option["platform_fit"]
        assert "Requires editorial review before use." in option["risk_notes"]
        assert "Must avoid misleading clickbait and unsupported claims." in option["risk_notes"]


def test_p25_title_options_helper_supports_explainer_and_rejects_invalid_inputs() -> None:
    options = build_title_options("World Cup 2026 pressure index", subject="World Cup 2026", content_type="explainer")
    assert len(options) == 10
    assert all(option["content_type"] == "explainer" for option in options)
    assert all("youtube_long_form" in option["platform_fit"] for option in options)

    with pytest.raises(ValueError):
        build_title_options("   ")

    with pytest.raises(ValueError):
        build_title_options("Neymar", content_type="podcast")  # type: ignore[arg-type]


def test_p25_title_options_example_contains_packaging_output_with_at_least_eight_options() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    options = example["packaging"]["title_options"]

    assert example["schema_version"] == "p24.content_package.v1"
    assert example["source_topic"] == "Neymar 2014 World Cup injury and comeback pressure"
    assert len(options) >= 8
    assert len(options) == 10
    assert {option["title_style"] for option in options} == set(TITLE_STYLES)

    for option in options:
        assert REQUIRED_FIELDS <= set(option)
        assert option["source_topic"] == example["source_topic"]
        assert option["approval_state"] == "not_approved"
        assert option["risk_notes"]


def test_p25_title_options_risk_rules_operator_review_guardrails_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "misleading clickbait",
        "unsupported injury claims",
        "unsupported scandal claims",
        "fabricated football facts",
        "fake certainty about future outcomes",
        "personal attacks on players, teams, fans, or communities",
        "implying rights, monetization, or editorial approval",
        "the title matches the script or concept",
        "the title does not overstate the facts",
        "the title is not misleading",
        "the title aligns with the first frame, thumbnail, hook, and CTA",
        "title options are marked approved automatically",
        "title options are uploaded to YouTube",
        "No misleading clickbait.",
        "No unsupported claims.",
        "No fabricated football facts.",
        "No automatic title approval.",
        "No automatic upload.",
        "No automatic publishing.",
        "No YouTube API A/B testing.",
        "No thumbnail generation in this step.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p25_step_*.py" in harness
