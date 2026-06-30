"""Tests for beat timeline planning and collage builder."""

from pathlib import Path

from PIL import Image

from src.assembler.explainer_assembler import _plan_beat_timeline
from src.config import Settings
from src.generator.collage_builder import build_four_player_collage
from src.generator.models import VisualBeat


def test_hook_loops_ai_beats_at_short_duration():
    settings = Settings()
    beats = [
        VisualBeat(duration_sec=0.7, visual_type="ai_image", ai_image_prompt="a"),
        VisualBeat(duration_sec=0.7, visual_type="ai_image", ai_image_prompt="b"),
    ]
    timeline = _plan_beat_timeline(beats, target_duration=3.5, settings=settings, section_type="hook")
    assert len(timeline) == 5
    assert all(duration <= settings.hook_beat_sec + 0.01 for _, _, duration in timeline)
    assert abs(sum(duration for _, _, duration in timeline) - 3.5) < 0.1


def test_entity_block_caps_stills_and_extends_clips():
    settings = Settings()
    beats = [
        VisualBeat(duration_sec=2.0, visual_type="web_image", image_search_query="player"),
        VisualBeat(duration_sec=2.5, visual_type="clip", clip_file="clip.mp4"),
        VisualBeat(duration_sec=2.0, visual_type="web_image", image_search_query="goal"),
        VisualBeat(duration_sec=2.5, visual_type="clip", clip_file="clip2.mp4"),
    ]
    timeline = _plan_beat_timeline(beats, target_duration=18.0, settings=settings, section_type="entity_block")
    durations = [duration for _, _, duration in timeline]
    assert durations[0] <= settings.max_still_beat_sec + 0.01
    assert durations[2] <= settings.max_still_beat_sec + 0.01
    assert durations[1] > 2.5
    assert durations[3] > 2.5
    assert abs(sum(durations) - 18.0) < 0.15


def test_build_four_player_collage(tmp_path: Path):
    paths: list[Path] = []
    for index in range(4):
        path = tmp_path / f"player_{index}.png"
        color = (40 + index * 40, 80, 120)
        Image.new("RGB", (800, 1200), color).save(path)
        paths.append(path)
    out = tmp_path / "collage.png"
    build_four_player_collage(paths, out, canvas_w=1080, canvas_h=1920)
    assert out.exists()
    collage = Image.open(out)
    assert collage.size == (1080, 1920)
