import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p67_real_facebook_manifest_is_present() -> None:
    manifest_path = ROOT / "reference-engine" / "pilots" / "p67-facebook-sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["rights_declaration"] == "public-internal-research"
    assert manifest["source_media_policy"] == "temporary-analysis-only-do-not-commit-or-republish"
    assert len(manifest["sources"]) == 5
    assert any("/reel/865258312526732" in item["url"] for item in manifest["sources"])


def test_p67_local_kokoro_is_default_voice_provider() -> None:
    dispatcher = (ROOT / "video-engine" / "scripts" / "generate-voice.mjs").read_text(
        encoding="utf-8"
    )
    generator = (
        ROOT / "video-engine" / "scripts" / "generate_voice_kokoro.py"
    ).read_text(encoding="utf-8")
    assert 'process.env.VOICE_PROVIDER || "kokoro"' in dispatcher
    assert "hexgrad/Kokoro-82M" in generator
    assert "local_no_per_character_fee" in generator


def test_p67_original_samples_require_human_review() -> None:
    sample_paths = [
        ROOT / "video-engine" / "samples" / "rawr-nation-blind-spot.json",
        ROOT / "video-engine" / "samples" / "animal-x-elephant-ground-signals.json",
    ]
    for path in sample_paths:
        project = json.loads(path.read_text(encoding="utf-8"))
        assert project["compositionId"] == "ReferenceStoryShort"
        assert project["humanReviewRequired"] is True
        assert project["editorialStatus"] == "demo_only_not_approved"
        assert project["voiceoverFile"] if "voiceoverFile" in project else True
        assert all(source["url"] for source in project["sources"])


def test_p67_workflow_does_not_publish_downloaded_source_media() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "p67-facebook-samples.yml"
    ).read_text(encoding="utf-8")
    assert "Confirm no source video enters artifacts" in workflow
    assert "p67-original-narrated-samples" in workflow
    assert "p67-facebook-reference-analysis" in workflow
    assert "vercel" not in workflow.lower()


def test_p67_reference_builder_preserves_anti_copy_constraints() -> None:
    builder = (
        ROOT / "reference-engine" / "scripts" / "p67_build_sample_project.py"
    ).read_text(encoding="utf-8")
    assert "source footage and frame composition" in builder
    assert "sourceMediaUsedInRender" in builder
    assert '"mechanicsOnly": True' in builder
