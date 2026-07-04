import pytest

from src.assembler.mode_assembler import validate_short_form_publish_plan
from src.generator.models import ProductionPlan, ScriptSegment


def test_logo_only_intro_is_rejected_for_publish() -> None:
    plan = ProductionPlan(
        title="Test",
        topic="Test",
        segments=[
            ScriptSegment(
                order=0,
                type="intro",
                narration="",
                target_duration_sec=4.0,
            ),
            ScriptSegment(order=1, type="clip", clip_file="clip.mp4"),
        ],
    )
    with pytest.raises(ValueError, match="logo-only"):
        validate_short_form_publish_plan(plan)


def test_hook_narration_starts_as_first_segment() -> None:
    plan = ProductionPlan(
        title="Test",
        topic="Test",
        segments=[
            ScriptSegment(
                order=0,
                type="intro",
                narration="This is the hook.",
                target_duration_sec=4.0,
            )
        ],
    )
    validate_short_form_publish_plan(plan)
