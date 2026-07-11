import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "video-engine"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p65_expected_files_exist():
    expected = [
        ENGINE / "package.json",
        ENGINE / "tsconfig.json",
        ENGINE / ".env.example",
        ENGINE / "README.md",
        ENGINE / "src" / "index.ts",
        ENGINE / "src" / "Root.tsx",
        ENGINE / "src" / "types.ts",
        ENGINE / "src" / "RawrNationShort.tsx",
        ENGINE / "scripts" / "validate-project.mjs",
        ENGINE / "scripts" / "generate-voice.mjs",
        ENGINE / "scripts" / "render.mjs",
        ENGINE / "samples" / "rawr-nation-army-ants.json",
    ]
    for path in expected:
        assert path.exists(), f"missing {path}"


def test_video_engine_is_isolated_and_remotion_based():
    package = json.loads(read(ENGINE / "package.json"))
    assert package["private"] is True
    assert package["scripts"]["render"]
    assert package["scripts"]["studio"]
    assert "remotion" in package["dependencies"]
    assert "@remotion/renderer" in package["dependencies"]
    assert "@remotion/bundler" in package["dependencies"]


def test_sample_project_is_real_vertical_video_contract():
    project = json.loads(read(ENGINE / "samples" / "rawr-nation-army-ants.json"))
    assert project["schemaVersion"] == "p65.video_project.v1"
    assert project["brand"]["id"] == "rawr_nation"
    assert project["format"] == "vertical_short"
    assert project["render"] == {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "codec": "h264",
        "durationSeconds": 36,
    }
    assert len(project["scenes"]) >= 5
    assert len(project["captions"]) >= 5
    assert project["sources"]
    assert project["humanReviewRequired"] is True
    assert project["editorialStatus"] == "demo_only_not_approved"


def test_composition_contains_motion_caption_brand_and_audio_layers():
    composition = read(ENGINE / "src" / "RawrNationShort.tsx")
    required = [
        "useCurrentFrame",
        "useVideoConfig",
        "Audio",
        "staticFile",
        "Caption",
        "VisualStage",
        "SwarmVisual",
        "BridgeVisual",
        "RevealVisual",
        "RAWR NATION",
        "human review required",
    ]
    for marker in required:
        assert marker in composition


def test_voice_adapter_uses_secrets_and_timing_endpoint():
    script = read(ENGINE / "scripts" / "generate-voice.mjs")
    assert "ELEVENLABS_API_KEY" in script
    assert "ELEVENLABS_VOICE_ID" in script
    assert "/with-timestamps" in script
    assert "audio_base64" in script
    assert "caption_only_fallback" in script
    assert "xi-api-key" in script
    assert "sk-" not in script


def test_render_command_exports_h264_mp4_and_manifest():
    script = read(ENGINE / "scripts" / "render.mjs")
    required = [
        "bundle",
        "selectComposition",
        "renderMedia",
        'codec: "h264"',
        'pixelFormat: "yuv420p"',
        'audioCodec: "aac"',
        ".mp4",
        "p65.render_result.v1",
        "Human review is required",
    ]
    for marker in required:
        assert marker in script


def test_runbook_states_current_scope_and_no_publish_boundary():
    docs = read(ENGINE / "README.md")
    assert "genuinely renders an MP4" in docs
    assert "caption-led and silent" in docs
    assert "ElevenLabs" in docs
    assert "No automatic publishing" in docs
    assert "Human editorial and policy review remains required" in docs
