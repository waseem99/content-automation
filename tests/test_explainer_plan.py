"""Tests for explainer plan model."""

from src.generator.models import ExplainerPlan, ExplainerSection, VisualBeat


def test_explainer_plan_beat_duration_sum():
    section = ExplainerSection(
        id="messi",
        section_type="entity_block",
        entity_name="Lionel Messi",
        theme="The Final Chapter",
        keyword="THE LEGACY",
        narration="First, Lionel Messi.",
        target_duration_sec=22,
        beats=[
            VisualBeat(duration_sec=3, visual_type="ai_image", ai_image_prompt="silhouette"),
            VisualBeat(duration_sec=5, visual_type="clip", clip_file="messi_clip_01.mp4"),
            VisualBeat(duration_sec=4, visual_type="web_image", image_search_query="Messi Argentina"),
            VisualBeat(duration_sec=10, visual_type="ai_image", ai_image_prompt="timeline"),
        ],
    )
    assert section.beat_duration_sum() == 22


def test_explainer_plan_narrated_sections():
    plan = ExplainerPlan(
        concept_id="test",
        title="Test Explainer",
        sections=[
            ExplainerSection(
                id="hook",
                section_type="hook",
                narration="One is writing his final chapter.",
                target_duration_sec=10,
                beats=[VisualBeat(duration_sec=2, visual_type="ai_image")],
            ),
            ExplainerSection(
                id="messi",
                section_type="entity_block",
                entity_name="Lionel Messi",
                narration="First, Lionel Messi.",
                target_duration_sec=22,
                beats=[VisualBeat(duration_sec=5, visual_type="web_image")],
            ),
        ],
    )
    assert len(plan.narrated_sections()) == 2
    assert len(plan.entity_sections()) == 1
