from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cta_library import CTA_TYPES, apply_cta_options_to_packaging, build_cta_options


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p25-step-05.md")
EXAMPLE = Path("docs/operations/p25-cta-library-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_FIELDS = {
    "cta_id",
    "cta_type",
    "cta_text",
    "source_topic",
    "content_type",
    "focal_subject",
    "intent",
    "comment_trigger",
    "platform_fit",
    "risk_notes",
    "approval_state",
}


def test_p25_cta_library_contract_references_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #327. Closes #342 after the PR merges.",
        "docs/operations/p24-step-03.md",
        "docs/operations/p24-step-05.md",
        "docs/operations/p25-step-01.md",
        "docs/operations/p25-step-02.md",
        "docs/operations/p25-step-03.md",
        "docs/operations/p25-step-04.md",
        "src/cta_library.py",
        "docs/operations/p25-cta-library-example.json",
        "tests/integration/test_p25_step_05.py",
        "define a CTA/comment-trigger schema",
        "generate debate CTAs",
        "generate prediction CTAs",
        "generate loyalty CTAs",
        "generate ranking CTAs",
        "generate controversy CTAs",
        "generate legacy CTAs",
        "generate versus CTAs",
        "does not scrape comments",
        "does not moderate communities",
        "does not post comments",
        "does not approve CTAs",
        "does not publish content",
    ]:
        assert term in content


def test_p25_cta_library_schema_and_required_types_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "cta_id",
        "cta_type",
        "cta_text",
        "source_topic",
        "content_type",
        "focal_subject",
        "intent",
        "comment_trigger",
        "platform_fit",
        "risk_notes",
        "approval_state",
        "debate",
        "prediction",
        "loyalty",
        "ranking",
        "controversy",
        "legacy",
        "versus",
        "Be honest: are fans too harsh on Neymar?",
        "What happens next for Neymar?",
        "Neymar fans, are you still backing this story?",
        "Rank Neymar by pressure, not talent.",
        "Is the conversation around Neymar fair or exaggerated?",
        "Does this change how you see Neymar’s legacy?",
        "Who carries more pressure than Neymar right now?",
    ]:
        assert term in content


def test_p25_cta_library_helper_generates_required_reviewable_options() -> None:
    topic = "Neymar 2014 World Cup injury and comeback pressure"
    options = build_cta_options(topic, subject="Neymar", content_type="short")

    assert len(options) == len(CTA_TYPES)
    assert {option["cta_type"] for option in options} == set(CTA_TYPES)

    for option in options:
        assert REQUIRED_FIELDS <= set(option)
        assert option["source_topic"] == topic
        assert option["content_type"] == "short"
        assert option["focal_subject"] == "Neymar"
        assert option["cta_text"]
        assert option["intent"]
        assert option["comment_trigger"]
        assert "youtube_shorts" in option["platform_fit"]
        assert "youtube_long_form" in option["platform_fit"]
        assert option["approval_state"] == "not_approved"
        assert "Requires editorial review before use." in option["risk_notes"]
        assert "Must avoid unsupported claims, harassment, and inflammatory wording." in option["risk_notes"]
        assert "Must not bait abuse toward players, teams, fans, or communities." in option["risk_notes"]


def test_p25_cta_library_helper_supports_content_types_and_rejects_invalid_inputs() -> None:
    options = build_cta_options("World Cup 2026 pressure index", subject="World Cup 2026", content_type="explainer")
    assert len(options) == len(CTA_TYPES)
    assert all(option["content_type"] == "explainer" for option in options)

    with pytest.raises(ValueError):
        build_cta_options("   ")

    with pytest.raises(ValueError):
        build_cta_options("Neymar", subject="   ")

    with pytest.raises(ValueError):
        build_cta_options("Neymar", content_type="podcast")  # type: ignore[arg-type]


def test_p25_cta_library_package_integration_is_review_only() -> None:
    package = {
        "package_id": "pkg-cta-integration",
        "packaging": {
            "title_options": [],
            "cta_comment_trigger_options": [],
            "status": "pending_p25",
            "planned_epic": "P25",
        },
        "editorial_review": {
            "approval_state": "not_approved",
        },
    }
    options = build_cta_options("Neymar 2014 World Cup injury and comeback pressure", subject="Neymar")
    updated = apply_cta_options_to_packaging(package, options)

    assert updated is not package
    assert updated["packaging"]["cta_comment_trigger_options"] == options
    assert updated["packaging"]["status"] == "generated_pending_review"
    assert updated["packaging"]["planned_epic"] == "P25"
    assert updated["editorial_review"]["approval_state"] == "not_approved"


def test_p25_cta_library_example_contains_all_required_cta_types() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    options = example["packaging"]["cta_comment_trigger_options"]

    assert example["schema_version"] == "p24.content_package.v1"
    assert example["source_topic"] == "Neymar 2014 World Cup injury and comeback pressure"
    assert len(options) == len(CTA_TYPES)
    assert {option["cta_type"] for option in options} == set(CTA_TYPES)

    for option in options:
        assert REQUIRED_FIELDS <= set(option)
        assert option["approval_state"] == "not_approved"
        assert option["risk_notes"]


def test_p25_cta_library_risk_rules_stop_conditions_guardrails_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "unsupported claims",
        "harassment",
        "inflammatory wording",
        "abusive fan-baiting",
        "personal attacks on players, teams, fans, or communities",
        "fake scandal framing",
        "fake injury framing",
        "hate, slurs, or protected-class targeting",
        "implying rights, monetization, or editorial approval",
        "the CTA matches the script and final segment",
        "the CTA does not encourage abuse",
        "CTA options are marked approved automatically",
        "CTA options scrape comments",
        "CTA options post comments",
        "No unsupported claims.",
        "No harassment.",
        "No inflammatory wording.",
        "No abusive fan-baiting.",
        "No fake injury framing.",
        "No fake scandal framing.",
        "No automatic CTA approval.",
        "No comment scraping.",
        "No comment posting.",
        "No automatic upload.",
        "No automatic publishing.",
        "No automatic monetization approval.",
        "No automatic rights clearance.",
        "No automatic editorial approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p25_step_*.py" in harness
