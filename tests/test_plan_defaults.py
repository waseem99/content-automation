"""Tests for prompt sanitizer and plan defaults."""

from pathlib import Path

from src.concepts.loader import load_concept
from src.generator.models import ExplainerPlan, ExplainerSection, VisualBeat
from src.generator.plan_defaults import ensure_plan_beats
from src.generator.prompt_sanitizer import sanitize_ai_prompt


def test_sanitize_removes_player_names():
    prompt = "Messi Argentina legacy and Mbappe France record chase"
    result = sanitize_ai_prompt(prompt)
    assert "messi" not in result.lower()
    assert "mbappe" not in result.lower()


def test_comparison_uses_web_plus_cinematic_edit():
    plan = ExplainerPlan(
        concept_id="test",
        title="Test",
        sections=[
            ExplainerSection(
                id="comparison",
                section_type="comparison",
                keyword="FOUR DIFFERENT PRESSURES",
                narration="Messi carries legacy.",
                target_duration_sec=14,
                beats=[
                    VisualBeat(
                        duration_sec=3,
                        visual_type="ai_image",
                        ai_image_prompt="Messi Argentina legacy",
                    )
                ],
            ),
        ],
    )
    concept = load_concept(Path("concepts/four_hyped_players_wc2026.yaml"))
    assert ensure_plan_beats(plan, concept) is True
    assert len(plan.sections[0].beats) == 4
    assert plan.sections[0].beats[-1].cinematic_edit is True
