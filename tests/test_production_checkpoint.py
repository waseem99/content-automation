"""Tests for production checkpoint."""

from pathlib import Path

from src.production_checkpoint import ProductionCheckpoint


def test_checkpoint_save_and_load(tmp_path: Path):
    path = tmp_path / "checkpoint.json"
    cp = ProductionCheckpoint(concept_id="test_concept")
    cp.mark_script_completed("test_concept")
    cp.mark_image_completed("hook_00")
    cp.mark_voice_completed("hook")
    cp.voice_id = "abc123"
    cp.voice_name = "Daniel"
    cp.save(path)

    loaded = ProductionCheckpoint.load(path)
    assert loaded.script == "completed"
    assert loaded.images["hook_00"] == "completed"
    assert loaded.voice["hook"] == "completed"
    assert loaded.voice_id == "abc123"


def test_resolve_voice_picks_premade_from_account():
    from src.generator.voice_generator import resolve_voice_id

    voices = [
        {"voice_id": "premade1", "name": "Daniel", "category": "premade"},
        {"voice_id": "bad_lib", "name": "Celebrity", "category": "premade"},
    ]

    def fake_list(_key: str):
        return voices

    import src.generator.voice_generator as vg

    original = vg.list_usable_voices
    vg.list_usable_voices = fake_list
    try:
        vid, name = resolve_voice_id("fake-key", "not_on_account")
        assert vid == "premade1"
        assert name == "Daniel"
        vid2, _ = resolve_voice_id("fake-key", "premade1")
        assert vid2 == "premade1"
    finally:
        vg.list_usable_voices = original
