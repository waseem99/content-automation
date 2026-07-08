from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p25-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p25_hook_retention_rubric_references_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #327. Closes #338 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p24-step-03.md",
        "docs/operations/p24-step-05.md",
        "src/content_package.py",
        ".github/workflows/p1-acceptance-harness.yml",
        "This rubric is documentation-only.",
        "generate titles",
        "generate thumbnails",
        "generate first-frame images",
        "generate videos",
        "score retention automatically",
        "call AI scoring services",
        "call YouTube analytics",
        "upload to YouTube",
        "publish content",
        "approve monetization",
        "approve rights",
        "approve editorial status",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p25_hook_retention_rubric_documents_score_scale_and_dimensions() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "0-2",
        "weak",
        "3-4",
        "needs_revision",
        "5-6",
        "usable_with_risk",
        "7-8",
        "strong",
        "9-10",
        "excellent",
        "first_1s_thumb_stop",
        "first_3s_clarity",
        "first_8s_retention_lock",
        "curiosity_gap",
        "visual_interruption",
        "emotional_stakes",
        "midpoint_reset",
        "cta_comment_trigger",
        "dead_air_risk",
        "genericness_risk",
    ]:
        assert term in content


def test_p25_hook_retention_rubric_documents_first_seconds_midpoint_and_cta_criteria() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "First 1 second criteria",
        "Who or what is visually on screen?",
        "sound off",
        "freeze-frame on a tackle",
        "stat-card shock number",
        "First 3 seconds criteria",
        "Which football person, team, or event is this about?",
        "What is the promise of the video?",
        "Visual interruption + specific subject + clear stakes",
        "First 8 seconds criteria",
        "the central question",
        "one surprising or emotionally loaded detail",
        "delays background until after the viewer understands the stakes",
        "Midpoint reset criteria",
        "new question",
        "player comparison",
        "timeline jump",
        "stat card",
        "but then",
        "Final CTA/comment-trigger criteria",
        "debate",
        "prediction",
        "ranking",
        "loyalty",
        "legacy",
        "rivalry",
        "versus",
        "pressure question",
    ]:
        assert term in content


def test_p25_hook_retention_rubric_includes_football_examples() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Neymar was injured in 2014.",
        "This tackle changed Neymar’s World Cup forever.",
        "Messi is old now.",
        "Messi may have one last World Cup question to answer.",
        "Mbappe is very fast.",
        "Mbappe is chasing a record most legends never touched.",
        "Yamal is a young player.",
        "Yamal is carrying pressure most teenagers never survive.",
        "Brazil had a bad game.",
        "Brazil’s World Cup broke in one brutal sequence.",
        "Be honest: is this Messi’s last real World Cup moment?",
        "Who carries more pressure in 2026: Mbappe or Messi?",
        "Rank these four by pressure, not talent.",
        "Was Neymar robbed of the legacy people expected?",
        "What do you think?",
        "Follow for more.",
    ]:
        assert term in content


def test_p25_hook_retention_rubric_documents_future_retention_score_contract_and_fixes() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Future retention_score.json contract",
        "hook_score",
        "first_1s_thumb_stop_score",
        "first_3s_clarity_score",
        "first_8s_retention_lock_score",
        "curiosity_gap_score",
        "visual_pacing_score",
        "emotional_stakes_score",
        "midpoint_reset_score",
        "cta_strength_score",
        "dead_air_risk",
        "genericness_risk",
        "recommended_fixes",
        "status",
        "planned_epic",
        "pending_p25",
        "Recommended fixes library",
        "open with the visual incident instead of background context",
        "replace a generic claim with a specific football moment",
        "add a comparison or stat card before the midpoint",
        "shorten the intro voiceover",
        "add a stronger first-frame caption",
        "replace “what do you think” with a debate question",
        "move factual context after the curiosity gap",
        "add a visual reset before viewer fatigue",
    ]:
        assert term in content


def test_p25_hook_retention_rubric_documents_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "No misleading clickbait.",
        "No unsupported claims.",
        "No fabricated football facts.",
        "No harassment of players, teams, fans, or communities.",
        "No implying injury, scandal, or controversy without source support.",
        "No publish approval from a retention score.",
        "No monetization approval from a retention score.",
        "No rights clearance from a retention score.",
        "No automatic upload.",
        "No automatic publishing.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p25_step_*.py" in harness
