from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p26-step-05.md")
EXAMPLE = Path("docs/operations/p26-publish-block-examples.json")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")

REQUIRED_FIELDS = {
    "decision_id",
    "package_id",
    "content_type",
    "publish_allowed",
    "review_required",
    "decision_state",
    "hard_blockers",
    "non_blocking_warnings",
    "blocking_reasons",
    "required_actions",
    "p29_editorial_required",
    "reviewer_role",
    "notes",
}

DECISION_STATES = {
    "blocked_until_review",
    "blocked_until_revision",
    "review_required",
    "export_candidate_after_review",
    "not_publish_ready",
}

HARD_BLOCKERS = {
    "unreviewed_broadcast_footage",
    "unreviewed_extracted_clip",
    "missing_image_attribution",
    "unknown_image_license",
    "unverified_music_license",
    "missing_stat_source_reference",
    "high_reused_content_risk",
    "missing_originality_layer",
    "missing_human_editorial_approval",
    "missing_p29_publish_readiness_manifest",
    "unreviewed_ai_likeness_or_logo_risk",
    "source_evidence_treated_as_clearance",
    "platform_export_requested_before_review",
    "legal_or_monetization_approval_implied",
}

NON_BLOCKING_WARNINGS = {
    "minor_caption_cleanup_needed",
    "optional_description_attribution_improvement",
    "low_confidence_title_variant",
    "thumbnail_concept_needs_polish",
    "cta_could_be_stronger",
    "retention_score_medium_risk",
    "internal_evidence_link_missing_pr_reference",
}


def test_p26_publish_block_rules_reference_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #328. Closes #348 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-step-01.md",
        "docs/operations/p26-step-02.md",
        "docs/operations/p26-step-03.md",
        "docs/operations/p26-step-04.md",
        "docs/operations/p26-publish-block-examples.json",
        "src/content_package.py",
        "tests/integration/test_p26_step_05.py",
        "This publish-block model is a workflow control.",
        "legal clearance",
        "copyright clearance",
        "monetization approval",
        "platform approval",
        "editorial approval",
        "direct platform enforcement",
        "automatic content removal",
        "automatic publishing",
        "automatic upload",
        "workflow gate bypass",
    ]:
        assert term in content


def test_p26_publish_block_rules_document_required_fields_states_blockers_and_warnings() -> None:
    content = DOC.read_text(encoding="utf-8")
    for field in REQUIRED_FIELDS:
        assert f"`{field}`" in content

    for state in DECISION_STATES:
        assert f"`{state}`" in content

    for blocker in HARD_BLOCKERS:
        assert f"`{blocker}`" in content

    for warning in NON_BLOCKING_WARNINGS:
        assert f"`{warning}`" in content

    assert "A decision state must not imply public release approval." in content
    assert "Non-blocking warnings must still be visible in the package and risk report." in content


def test_p26_publish_block_rules_document_blocking_condition_details() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Unreviewed broadcast footage",
        "Any broadcast clip, match highlight, match still, or extracted source clip with unresolved rights must block publishing.",
        "Missing image attribution or unknown image license",
        "Any web image with unknown license, unknown attribution requirement, missing source page, or unresolved player/logo/trademark risk must block publishing.",
        "Unverified music license",
        "Any music or sound asset with unknown commercial/social/platform coverage must block publishing.",
        "Missing source references",
        "Any statistic, claim, ranking, factual comparison, or caption claim without source references must block publishing.",
        "High reused-content risk",
        "A package with raw clips, generic narration, low originality, or slideshow-style assembly must block publishing.",
        "Missing human approval",
        "No package can be publish-ready before P29 editorial governance exists and a human reviewer approves the publish-readiness manifest.",
    ]:
        assert term in content


def test_p26_publish_block_rules_document_report_fields_p29_alignment_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Required report fields",
        "`publish_allowed`",
        "`review_required`",
        "`blocking_reasons`",
        "`required_actions`",
        "`hard_blockers`",
        "`non_blocking_warnings`",
        "`decision_state`",
        "`p29_editorial_required`",
        "Alignment with P29 editorial workflow",
        "editorial status model",
        "human review checklist",
        "publish-readiness manifest",
        "render-mode approval rules",
        "editorial evidence trail",
        "final approval state",
        "Until P29 is complete, `missing_p29_publish_readiness_manifest` and `missing_human_editorial_approval` remain hard blockers.",
        "No legal clearance implied.",
        "No copyright clearance implied.",
        "No monetization approval implied.",
        "No platform approval implied.",
        "No editorial approval implied.",
        "No direct platform enforcement.",
        "No auto-removing risky content.",
        "No automatic upload.",
        "No automatic publishing.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content


def test_p26_publish_block_examples_have_required_shape_and_publish_allowed_false() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert example["schema_version"] == "p26.publish_block_rules.v1"
    assert example["package_id"] == "pkg-publish-block-examples"
    decisions = example["decisions"]
    assert len(decisions) == 3

    for decision in decisions:
        assert REQUIRED_FIELDS <= set(decision)
        assert decision["decision_state"] in DECISION_STATES
        assert decision["publish_allowed"] is False
        assert decision["review_required"] is True
        assert decision["p29_editorial_required"] is True
        assert decision["blocking_reasons"]
        assert decision["required_actions"]
        assert decision["notes"]


def test_p26_publish_block_examples_cover_blocked_review_and_export_candidate_states() -> None:
    decisions = {decision["decision_id"]: decision for decision in json.loads(EXAMPLE.read_text(encoding="utf-8"))["decisions"]}

    high = decisions["blocked_high_risk_package"]
    assert high["decision_state"] == "blocked_until_review"
    assert {
        "unreviewed_broadcast_footage",
        "unverified_music_license",
        "missing_stat_source_reference",
        "high_reused_content_risk",
        "missing_originality_layer",
        "missing_human_editorial_approval",
        "missing_p29_publish_readiness_manifest",
    } <= set(high["hard_blockers"])

    medium = decisions["medium_review_required_package"]
    assert medium["decision_state"] == "review_required"
    assert "missing_image_attribution" in medium["hard_blockers"]
    assert "thumbnail_concept_needs_polish" in medium["non_blocking_warnings"]
    assert "retention_score_medium_risk" in medium["non_blocking_warnings"]

    export_candidate = decisions["export_candidate_after_review_package"]
    assert export_candidate["decision_state"] == "export_candidate_after_review"
    assert "missing_human_editorial_approval" in export_candidate["hard_blockers"]
    assert "missing_p29_publish_readiness_manifest" in export_candidate["hard_blockers"]
    assert "publish_allowed remains false until final approval exists." in export_candidate["notes"]


def test_p26_publish_block_stop_conditions_and_ci_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "a high-risk example has `publish_allowed: true`",
        "unreviewed broadcast footage is non-blocking",
        "unverified music is non-blocking",
        "missing image attribution is non-blocking",
        "missing source references are non-blocking",
        "missing originality is non-blocking",
        "missing human editorial approval is non-blocking",
        "P29 approval is bypassed",
        "direct platform enforcement is introduced",
        "auto-removing risky content is introduced",
        "workflow gate bypass is requested",
    ]:
        assert term in content

    assert "tests/integration/test_p26_step_*.py" in harness
