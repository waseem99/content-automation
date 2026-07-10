import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = ROOT / "web" / "static-creator-ui"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_static_ui_expected_files_exist():
    expected = [
        STATIC_ROOT / "index.html",
        STATIC_ROOT / "assets" / "styles.css",
        STATIC_ROOT / "assets" / "app.js",
        STATIC_ROOT / "assets" / "engine-map.js",
        STATIC_ROOT / "sample-brief.json",
        STATIC_ROOT / "wordpress-embed.html",
        STATIC_ROOT / "vercel.json",
        ROOT / "vercel.json",
        ROOT / ".vercelignore",
        ROOT / "package.json",
        ROOT / "scripts" / "build-static-creator-ui.js",
        ROOT / "docs" / "operations" / "p62-vercel-static-ui.md",
        ROOT / "docs" / "operations" / "p64-interactive-content-engine-map.md",
    ]
    for path in expected:
        assert path.exists(), f"missing {path}"


def test_index_uses_local_assets_only():
    html = read(STATIC_ROOT / "index.html")
    assert 'href="assets/styles.css"' in html
    assert 'src="assets/engine-map.js"' in html
    assert 'src="assets/app.js"' in html
    assert "https://" not in html
    assert "http://" not in html
    assert "cdn" not in html.lower()


def test_interactive_engine_map_is_present_and_decision_oriented():
    html = read(STATIC_ROOT / "index.html")
    required_ids = [
        'id="engine-map"',
        'id="engine-stage-rail"',
        'id="engine-detail"',
        'id="engine-platform"',
        'id="platform-detail"',
    ]
    for identifier in required_ids:
        assert identifier in html
    assert "Engagement assurance loop" in html
    assert "Policy assurance loop" in html
    assert "Monetization assurance loop" in html
    assert "Human controlled" in html
    assert "Next architecture layer" in html


def test_engine_map_js_covers_pipeline_objectives_and_platforms():
    engine = read(STATIC_ROOT / "assets" / "engine-map.js")
    blocked_terms = ["fetch(", "XMLHttpRequest", "import(", "axios", "apiKey", "api_key"]
    for term in blocked_terms:
        assert term not in engine
    for stage in [
        "Brief & Intent Capture",
        "Content Strategy & Platform Adaptation",
        "Hook, Script & Storyboard Generation",
        "Rights, Safety & Policy Gate",
        "Engagement & Retention Scoring",
        "Monetization Readiness",
        "Production Handoff & Batch Execution",
        "Human Review, Feedback & Revision",
        "Export, Measurement & Learning Loop",
    ]:
        assert stage in engine
    for objective in ["engagement", "policy", "monetization"]:
        assert objective in engine.lower()
    for platform in ["youtube_shorts", "instagram_reels", "tiktok", "youtube_long", "linkedin_video"]:
        assert platform in engine
    for module in ["P40", "P41", "P42", "P44", "P46", "P50", "P54", "P58", "P62"]:
        assert module in engine


def test_app_js_is_browser_only_without_external_calls():
    app = read(STATIC_ROOT / "assets" / "app.js")
    blocked_terms = ["fetch(", "XMLHttpRequest", "import(", "axios", "openai", "apiKey", "api_key"]
    for term in blocked_terms:
        assert term not in app
    assert "buildReviewPack" in app
    assert "navigator.clipboard" in app
    assert "URL.createObjectURL" in app


def test_subdirectory_vercel_config_forces_static_framework():
    config = json.loads(read(STATIC_ROOT / "vercel.json"))
    assert config["framework"] is None
    assert config["installCommand"] == ""
    assert config["buildCommand"] is None
    assert config["outputDirectory"] == "."
    rewrites = config["rewrites"]
    assert {"source": "/", "destination": "/index.html"} in rewrites
    assert {"source": "/app", "destination": "/index.html"} in rewrites
    assert {"source": "/assets/:path*", "destination": "/assets/:path*"} in rewrites
    assert {"source": "/sample-brief.json", "destination": "/sample-brief.json"} in rewrites
    assert any(header["source"] == "/assets/:path*" for header in config["headers"])


def test_root_vercel_config_forces_other_and_static_build_output():
    config = json.loads(read(ROOT / "vercel.json"))
    assert config["framework"] is None
    assert config["installCommand"] == ""
    assert config["buildCommand"] == "npm run build"
    assert config["outputDirectory"] == "dist"
    rewrites = config["rewrites"]
    assert {"source": "/", "destination": "/index.html"} in rewrites
    assert {"source": "/app", "destination": "/index.html"} in rewrites
    assert {"source": "/assets/:path*", "destination": "/assets/:path*"} in rewrites


def test_vercelignore_blocks_python_fastapi_detection_files():
    ignore = read(ROOT / ".vercelignore")
    blocked = [
        "src/",
        "tests/",
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
    ]
    for entry in blocked:
        assert entry in ignore
    assert "!web/static-creator-ui/**" in ignore
    assert "!vercel.json" in ignore
    assert "!package.json" in ignore


def test_package_json_locks_static_node_build():
    package = json.loads(read(ROOT / "package.json"))
    assert package["private"] is True
    assert package["scripts"]["build"] == "node scripts/build-static-creator-ui.js"
    assert package["dependencies"] == {}
    assert package["devDependencies"] == {}


def test_static_build_script_copies_expected_dist_files():
    script = read(ROOT / "scripts" / "build-static-creator-ui.js")
    assert "web" in script
    assert "static-creator-ui" in script
    assert "dist" in script
    assert "index.html" in script
    assert "assets" in script
    assert "Static Creator UI copied" in script


def test_sample_brief_is_valid_and_guarded():
    sample = json.loads(read(STATIC_ROOT / "sample-brief.json"))
    assert sample["topic"]
    assert sample["platform"] == "youtube_shorts"
    assert sample["duration_seconds"] > 0
    assert sample["must_use_points"]
    assert sample["avoid"]


def test_docs_explain_vercel_framework_override_and_guardrails():
    docs = read(ROOT / "docs" / "operations" / "p62-vercel-static-ui.md")
    assert "Vercel" in docs
    assert "framework: null" in docs
    assert "Framework Preset: Other" in docs
    assert ".vercelignore" in docs
    assert "FastAPI" in docs
    assert "Human review remains required" in docs
    assert "does not call a server-side AI model" in docs


def test_engine_map_docs_explain_strategy_and_limitations():
    docs = read(ROOT / "docs" / "operations" / "p64-interactive-content-engine-map.md")
    for phrase in [
        "Engagement",
        "Policy compliance",
        "Monetization",
        "P59–P61",
        "P40–P45",
        "P46–P53",
        "P54–P58",
        "P62–P64",
        "Human approval",
        "Future AI/backend",
    ]:
        assert phrase in docs
