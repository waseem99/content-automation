from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p26-step-04.md")
EXAMPLE = Path("docs/operations/p26-originality-layer-example.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_SIGNALS = {
    "unique_narration_angle",
    "original_analysis",
    "custom_stat_card",
    "sourced_comparison",
    "human_editorial_view",
    "custom_graphic_or_visual_structure",
    "host_or_avatar_layer",
    "contextual_timeline",
    "counterpoint_or_nuance",
    "original_cta_or_debate_frame",
}

REQUIRED_SIGNAL_FIELDS = {
    "signal_id",
    "signal_type",
    "description",
    "evidence_path",
    "source_reference",
    "strength",
    "review_required",
    "review_status",
    "notes",
}

REQUIRED_REPORT_FIELDS = {
    "schema_version",
    "package_id",
    "content_type",
    "originality_score",
    "originality_status",
    "signals_present",
    "signals_missing",
    "generic_template_warnings",
    "required_actions",
    "review_required",
    "approval_state",
    "notes",
}


def test_p26_originality_requirements_reference_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #328. Closes #347 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-step-01.md",
        "docs/operations/p26-step-02.md",
        "docs/operations/p26-step-03.md",
        "src/content_package.py",
        "docs/operations/p26-originality-layer-example.json",
        "tests/integration/test_p26_step_04.py",
        "This originality model is documentation and contract focused.",
        "rewrite videos automatically",
        "create a full creative rewrite engine",
        "generate a human host or avatar",
        "approve monetization",
        "approve rights",
        "approve publishing",
        "clear reused-content risk automatically",
        "upload to any platform",
        "publish content",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p26_originality_requirements_document_signals_schema_and_statuses() -> None:
    content = DOC.read_text(encoding="utf-8")
    for signal in REQUIRED_SIGNALS:
        assert f"`{signal}`" in content

    for field in REQUIRED_SIGNAL_FIELDS:
        assert f"`{field}`" in content

    for term in [
        "weak",
        "moderate",
        "strong",
        "not_started",
        "drafted",
        "review_required",
        "revision_required",
        "reviewed_pending_editorial",
        "approved_for_editorial_review",
        "`approved_for_editorial_review` does not mean publish approval.",
    ]:
        assert term in content


def test_p26_originality_requirements_document_shorts_and_explainer_minimums() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Minimum originality requirements for Shorts",
        "A Short must include at least three originality signals",
        "one `unique_narration_angle` or `original_analysis` signal",
        "one `custom_stat_card`, `sourced_comparison`, `contextual_timeline`, or `custom_graphic_or_visual_structure` signal",
        "one `original_cta_or_debate_frame`, `counterpoint_or_nuance`, or `human_editorial_view` signal",
        "a raw clip",
        "a clip montage",
        "a generic AI voiceover",
        "a slideshow of web images",
        "a copied headline with captions",
        "a template with swapped player names",
        "Minimum originality requirements for explainers",
        "An explainer must include at least five originality signals",
        "one `sourced_comparison` or `custom_stat_card` signal",
        "one `contextual_timeline` or `counterpoint_or_nuance` signal",
        "a listicle with no original framing",
        "generic facts read over stock images",
        "repeated template sections for each player",
        "AI-generated narration with no editorial point of view",
    ]:
        assert term in content


def test_p26_originality_requirements_document_warning_signs_examples_and_score_bands() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Generic-template warning signs",
        "the same sentence structure repeats for every player",
        "the narration could apply to any footballer",
        "no claim has a source reference",
        "no counterpoint or nuance is included",
        "the package depends mainly on broadcast footage or web images",
        "Weak versus stronger football framing",
        "Neymar is a great player.",
        "Neymar’s legacy is judged through one injury, one expectation, and one unfinished World Cup question.",
        "Messi is old now.",
        "Messi’s 2026 question is not age alone; it is whether Argentina still needs him as a creator or symbol.",
        "Mbappe is fast.",
        "Mbappe’s pressure is different because he is chasing history while already being treated like the standard.",
        "Originality score bands",
        "0-2",
        "3-4",
        "5-6",
        "7-8",
        "9-10",
    ]:
        assert term in content


def test_p26_originality_requirements_document_report_fields_and_linkages() -> None:
    content = DOC.read_text(encoding="utf-8")
    for field in REQUIRED_REPORT_FIELDS:
        assert f"`{field}`" in content

    for term in [
        "monetization_risk_report.json linkage",
        "`risk_categories.originality_risk.risk_level`",
        "`risk_categories.originality_risk.review_required`",
        "`risk_categories.originality_risk.publish_blocking`",
        "`content_package_updates.originality_status`",
        "If originality is missing, `publish_allowed` must remain `false`.",
        "content_package.json linkage",
        "`packaging.title_options`",
        "`packaging.first_frame_options`",
        "`packaging.thumbnail_concepts`",
        "`packaging.cta_comment_trigger_options`",
        "`retention.genericness_risk`",
        "`rights_and_monetization.originality_status`",
        "Originality tracking can update package status to `originality_review_required` or `originality_blocked`, but it must not set `publish_allowed` to `true`.",
    ]:
        assert term in content


def test_p26_originality_example_has_required_shape_and_signals() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert example["schema_version"] == "p26.originality_layer.v1"
    assert example["package_id"] == "pkg-originality-example"
    assert example["publish_allowed"] is False

    examples = example["examples"]
    assert {entry["example_id"] for entry in examples} == {
        "weak_short_example",
        "stronger_short_example",
        "stronger_explainer_example",
    }

    for entry in examples:
        assert entry["approval_state"] == "not_approved"
        assert entry["review_required"] is True
        assert "risk_report_linkage" in entry
        assert entry["risk_report_linkage"]["publish_blocking"] is True
        for signal in entry["signals_present"]:
            assert REQUIRED_SIGNAL_FIELDS <= set(signal)
            assert signal["signal_type"] in REQUIRED_SIGNALS
            assert signal["strength"] in {"weak", "moderate", "strong"}


def test_p26_originality_example_distinguishes_weak_and_stronger_outputs() -> None:
    examples = {entry["example_id"]: entry for entry in json.loads(EXAMPLE.read_text(encoding="utf-8"))["examples"]}

    weak = examples["weak_short_example"]
    assert weak["originality_score"] == 2
    assert weak["originality_status"] == "originality_blocked"
    assert "generic AI voiceover" in weak["generic_template_warnings"]
    assert "slideshow of web images" in weak["generic_template_warnings"]
    assert "unique_narration_angle" in weak["signals_missing"]

    stronger_short = examples["stronger_short_example"]
    assert stronger_short["originality_score"] == 7
    assert len(stronger_short["signals_present"]) >= 3
    assert {signal["signal_type"] for signal in stronger_short["signals_present"]} >= {
        "unique_narration_angle",
        "sourced_comparison",
        "original_cta_or_debate_frame",
    }

    stronger_explainer = examples["stronger_explainer_example"]
    assert stronger_explainer["originality_score"] == 8
    assert len(stronger_explainer["signals_present"]) >= 5
    assert {signal["signal_type"] for signal in stronger_explainer["signals_present"]} >= {
        "unique_narration_angle",
        "original_analysis",
        "custom_stat_card",
        "contextual_timeline",
        "counterpoint_or_nuance",
    }


def test_p26_originality_stop_conditions_guardrails_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "a raw clip is treated as original by default",
        "generic AI narration is treated as original by default",
        "a slideshow of web images is treated as original by default",
        "swapped player-name templates are treated as original by default",
        "originality score is treated as rights clearance",
        "originality score is treated as monetization approval",
        "originality score is treated as publish approval",
        "`publish_allowed` is changed to `true`",
        "upload or publishing is introduced",
        "workflow gate bypass is requested",
        "No automatic creative rewrite engine.",
        "No automatic host/avatar production.",
        "No automatic originality approval.",
        "No automatic reused-content clearance.",
        "No automatic monetization approval.",
        "No automatic rights clearance.",
        "No automatic publishing approval.",
        "No automatic upload.",
        "No automatic publishing.",
        "No unsupported claims.",
        "No misleading clickbait.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p26_step_*.py" in harness
