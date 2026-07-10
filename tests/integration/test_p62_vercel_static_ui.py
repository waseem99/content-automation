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
        STATIC_ROOT / "sample-brief.json",
        STATIC_ROOT / "wordpress-embed.html",
        STATIC_ROOT / "vercel.json",
        ROOT / "vercel.json",
        ROOT / ".vercelignore",
        ROOT / "package.json",
        ROOT / "scripts" / "build-static-creator-ui.js",
        ROOT / "docs" / "operations" / "p62-vercel-static-ui.md",
    ]
    for path in expected:
        assert path.exists(), f"missing {path}"


def test_index_uses_local_assets_only():
    html = read(STATIC_ROOT / "index.html")
    assert 'href="assets/styles.css"' in html
    assert 'src="assets/app.js"' in html
    assert "https://" not in html
    assert "http://" not in html
    assert "cdn" not in html.lower()


def test_app_js_is_browser_only_without_external_calls():
    app = read(STATIC_ROOT / "assets" / "app.js")
    blocked_terms = ["fetch(", "XMLHttpRequest", "import(", "axios", "openai", "apiKey", "api_key"]
    for term in blocked_terms:
        assert term not in app
    assert "buildReviewPack" in app
    assert "navigator.clipboard" in app
    assert "URL.createObjectURL" in app


def test_subdirectory_vercel_config_routes_static_ui():
    config = json.loads(read(STATIC_ROOT / "vercel.json"))
    rewrites = config["rewrites"]
    assert {"source": "/", "destination": "/index.html"} in rewrites
    assert {"source": "/app", "destination": "/index.html"} in rewrites
    assert {"source": "/assets/:path*", "destination": "/assets/:path*"} in rewrites
    assert {"source": "/sample-brief.json", "destination": "/sample-brief.json"} in rewrites
    assert any(header["source"] == "/assets/:path*" for header in config["headers"])


def test_root_vercel_config_uses_static_build_output_as_fallback():
    config = json.loads(read(ROOT / "vercel.json"))
    assert config["installCommand"].startswith("node -e")
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


def test_docs_explain_vercel_root_directory_and_guardrails():
    docs = read(ROOT / "docs" / "operations" / "p62-vercel-static-ui.md")
    assert "Vercel" in docs
    assert "Root Directory: web/static-creator-ui" in docs
    assert "Build Command: leave empty" in docs
    assert ".vercelignore" in docs
    assert "FastAPI" in docs
    assert "Human review remains required" in docs
    assert "does not call a server-side AI model" in docs
