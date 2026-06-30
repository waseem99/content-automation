"""Tests for production plan model."""

from src.generator.models import ProductionPlan, ScriptSegment


def test_production_plan_segment_order():
    plan = ProductionPlan(
        title="Test",
        topic="Neymar injury",
        segments=[
            ScriptSegment(order=1, type="image", image_index=1, narration="Hook"),
            ScriptSegment(order=2, type="clip", clip_file="clip_04.mp4", target_duration_sec=9),
            ScriptSegment(order=3, type="image", image_index=2, narration="Context"),
            ScriptSegment(order=4, type="clip", clip_file="clip_07.mp4", target_duration_sec=9),
            ScriptSegment(order=5, type="image", image_index=3, narration="Comeback"),
        ],
    )
    assert len(plan.image_segments()) == 3
    assert len(plan.clip_segments()) == 2
