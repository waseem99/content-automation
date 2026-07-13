from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "src" / "p68_continuity_planner.py"
DOC = ROOT / "docs" / "operations" / "p68-step-04.md"


def test_p68_step_04_engine_covers_originality_and_natural_continuity() -> None:
    content = ENGINE.read_text(encoding="utf-8")
    for term in [
        "generate_concept_options",
        "originality_distance",
        "continuity_bible",
        "build_shot_plan",
        "build_original_content_plan",
        "subject_identity",
        "environment_lock",
        "lighting",
        "screen_direction",
        "camera_language",
        "entry_action",
        "exit_action",
        "transition_handle_seconds",
        "audio_bridge",
        "color_treatment",
        "clip_prompt",
        "negative_prompt",
        '"render_allowed": False',
        '"publish_allowed": False',
    ]:
        assert term in content


def test_p68_step_04_documentation_keeps_generation_and_approval_separate() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #714. Closes #718 after the PR merges.",
        "three original concept options",
        "6–8 shots",
        "25–38 seconds",
        "at least 0.5 seconds",
        "subject identity",
        "environment and background",
        "lighting and time of day",
        "screen direction",
        "camera motion",
        "entry and exit action",
        "audio bridge",
        "color treatment",
        "source-backed factual notes",
        "source wording similarity",
        "does not generate clips",
        "does not approve rendering",
        "publish_allowed: false",
    ]:
        assert term in content
