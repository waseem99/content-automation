import json
from pathlib import Path

from src.p76_portfolio_bridge import (
    ArtifactCandidate,
    artifact_already_registered,
    discover_artifacts,
    load_pilot_workspace,
    materialize_artifact,
    safe_media_relative,
    workspace_changed,
)


ROOT = Path(__file__).resolve().parents[2]


def test_pilot_workspace_maps_script_scenes_and_voice(tmp_path: Path):
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    (pilot / "content-plan.json").write_text(json.dumps({
        "original_script": "A factual script.",
        "selected_concept": {"hook_direction": "Hook", "payoff_direction": "Payoff"},
        "shots": [{"shot_id": "S01"}],
    }))
    (pilot / "storyboard.json").write_text(json.dumps([{"shot_id": "S01", "visual": "Original visual"}]))
    (pilot / "voice-project.json").write_text(json.dumps({
        "narration": "A factual script.", "brand": {"voiceStyle": "clear"}, "render": {"durationSeconds": 9}
    }))
    workspace = load_pilot_workspace(pilot)
    assert workspace["script"]["text"] == "A factual script."
    assert workspace["scene_plan"]["scenes"] == [{"shot_id": "S01"}]
    assert workspace["voiceover"]["duration_seconds"] == 9


def test_artifact_discovery_prefers_hybrid_review_and_kokoro(tmp_path: Path):
    root = tmp_path / "gold" / "pilot"
    narration = root / "narration"
    hybrid = root / "renders" / "hybrid-v1"
    review = root / "renders" / "review-v1"
    keyframes = root / "generated-assets"
    for path in (narration, hybrid, review, keyframes):
        path.mkdir(parents=True, exist_ok=True)
    (narration / "voice.wav").write_bytes(b"voice")
    (hybrid / "final_review.mp4").write_bytes(b"hybrid")
    (review / "final_review.mp4").write_bytes(b"review")
    (hybrid / "render_manifest.json").write_text(json.dumps({"technical_pass": True, "probe": {"width": 1080}}))
    (keyframes / "S01.png").write_bytes(b"image")
    found = discover_artifacts(root)
    assert [item.kind for item in found] == ["voiceover", "preview", "keyframe"]
    assert found[1].source == hybrid / "final_review.mp4"
    assert found[1].metadata["technical_pass"] is True


def test_materialization_is_hash_named_safe_and_idempotent(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"review-video")
    candidate = ArtifactCandidate("preview", "Free preview", source, {"provider": "local"})
    relative = safe_media_relative(
        brand_slug="rawr-nation", content_id="abc-123", pilot_id="rawr-test", candidate=candidate
    )
    media_root = tmp_path / "media"
    first = materialize_artifact(candidate, media_root=media_root, relative=relative)
    second = materialize_artifact(candidate, media_root=media_root, relative=relative)
    assert first == second
    assert first["local_locator"].startswith("content://rawr-nation/abc-123/rawr-test/preview-source-")
    assert (media_root / relative).read_bytes() == b"review-video"


def test_sync_comparisons_avoid_duplicate_updates_and_artifacts():
    desired = {"script": {"text": "x"}, "scene_plan": {"scenes": []}, "voiceover": {"provider": "kokoro"}}
    assert workspace_changed(desired, desired) is False
    assert workspace_changed({}, desired) is True
    payload = {"kind": "preview", "sha256": "a" * 64}
    assert artifact_already_registered([payload], payload) is True
    assert artifact_already_registered([], payload) is False


def test_bridge_scripts_are_local_only_and_do_not_deploy_or_publish():
    sync = (ROOT / "scripts" / "p76_sync_pilot.py").read_text()
    doctor = (ROOT / "scripts" / "p76_local_production_doctor.py").read_text()
    assert "--dry-run" in sync
    assert "--confirm-editorial-match" in sync
    assert 'os.getenv("OPERATOR_KEY"' in sync
    assert "PORTFOLIO_MEDIA_ROOT" in sync
    assert "vercel" not in sync.lower()
    assert "/publish" not in sync
    assert '"vercel_required": False' in doctor
    assert '"paid_provider_required": False' in doctor
