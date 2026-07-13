from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.p68_scientific_animation import RENDERERS, render_animation


def test_required_mechanism_shots_have_deterministic_renderers() -> None:
    assert {shot for pilot, shot in RENDERERS if pilot == "rawr-blind-spot"} == {"S02", "S03", "S04", "S05", "S06"}
    assert {shot for pilot, shot in RENDERERS if pilot == "animal-elephant-signals"} == {"S03", "S04"}


def test_renderer_produces_real_portrait_motion_clip(tmp_path: Path) -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required")
    result = render_animation(RENDERERS[("rawr-blind-spot", "S05")], tmp_path / "dot-test.mp4", 0.4)
    assert result["width"] == 1080
    assert result["height"] == 1920
    assert result["fps"] == 30
    assert result["duration_seconds"] >= 0.35
