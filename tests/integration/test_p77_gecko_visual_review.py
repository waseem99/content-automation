from pathlib import Path

from src.p68_scientific_animation import ANIMATION_VERSION, RENDERERS


ROOT = Path(__file__).resolve().parents[2]


def test_gecko_has_six_distinct_code_authored_motion_scenes():
    keys = {(pilot, shot) for pilot, shot in RENDERERS if pilot == "rawr-gecko-grip"}
    assert keys == {("rawr-gecko-grip", f"S{index:02d}") for index in range(1, 7)}
    assert ANIMATION_VERSION == "p68.scientific_animation.v5"
    first_frames = [RENDERERS[("rawr-gecko-grip", f"S{index:02d}")](0.0) for index in range(1, 7)]
    assert all(frame.size == (540, 960) for frame in first_frames)
    assert len({frame.tobytes() for frame in first_frames}) == 6


def test_animation_renderer_stays_video_only_until_narration_stitching():
    source = (ROOT / "src" / "p68_scientific_animation.py").read_text()
    assert '"-an"' in source
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" not in source
    assert '"-c:a"' not in source
    assert '"aac"' not in source
    assert "return probe_media(output)" in source


def test_visual_review_is_explicitly_non_approvable_and_non_publishable():
    script = (ROOT / "scripts" / "p77_build_visual_review.py").read_text()
    assert '"review_scope": "visual_motion_and_storyboard_only"' in script
    assert '"narration_required": True' in script
    assert '"approval_allowed": False' in script
    assert '"publish_allowed": False' in script
    assert "/publish" not in script
    assert "vercel" not in script.lower()


def test_portfolio_bridge_can_discover_visual_review_without_claiming_voice():
    source = (ROOT / "src" / "p76_portfolio_bridge.py").read_text()
    assert '"visual-v1" / "final_review.mp4"' in source
