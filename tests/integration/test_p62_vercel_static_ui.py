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
        STATIC_ROOT / "assets" / "portfolio-api.js",
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


def test_interactive_engine_map_is_present_and_decision_oriented():
    html = read(STATIC_ROOT / "index.html")
    required = [
        'id="engine-map"',
        'id="engine-pipeline"',
        'id="engine-detail"',
        'data-filter="engagement"',
        'data-filter="compliance"',
        'data-filter="monetization"',
        "Runtime Lanes",
        "How output is controlled against the three objectives",
        "How the engine proves what happened",
        "Planned AI Generation Layer",
        'id="portfolio-studio"',
        'id="brand-filter"',
        'id="content-queue"',
        "30-Day Content Portfolio",
    ]
    for marker in required:
        assert marker in html


def test_portfolio_dashboard_exposes_brand_queue_and_approval_economics():
    app = read(STATIC_ROOT / "assets" / "app.js")
    required = [
        "portfolioBrands",
        "portfolioItems",
        "Rawr Nation",
        "Animal X",
        "News Brand",
        "monthlyTarget",
        "renderPortfolio",
        "bindPortfolioControls",
        "portfolio-30-day-plan.json",
        'primary: "facebook"',
        'approval_required: true',
    ]
    for marker in required:
        assert marker in app


def test_engine_map_js_tracks_modules_tools_outputs_and_quality_gates():
    app = read(STATIC_ROOT / "assets" / "app.js")
    required = [
        "P40 Package Generator",
        "P41 Rights & Safety",
        "P42 Engagement",
        "P44 Monetization",
        "P46 Producer Export",
        "P53 Comparator",
        "P58 Review Cycle",
        "P61 Full Cycle",
        "P62 Static UI",
        "P63 Vercel Lock",
        "objectives:",
        "gate:",
        "outputs:",
        "tools:",
        "renderEnginePipeline",
        "renderEngineDetail",
        "setEngineFilter",
    ]
    for marker in required:
        assert marker in app


def test_engine_map_discloses_current_and_planned_runtime_boundaries():
    app = read(STATIC_ROOT / "assets" / "app.js")
    html = read(STATIC_ROOT / "index.html")
    assert "Planned model adapter" in app
    assert "Planned Vercel API" in app
    assert "Not connected to the deployed static UI yet" in html
    assert "Human review remains required before production" in html
    assert "No database, automatic publishing, final approval, or external AI call" in html


def test_app_js_is_browser_only_without_external_calls():
    app = read(STATIC_ROOT / "assets" / "app.js")
    blocked_terms = ["fetch(", "XMLHttpRequest", "import(", "axios", "openai", "apiKey", "api_key"]
    for term in blocked_terms:
        assert term not in app
    assert "buildReviewPack" in app
    assert "navigator.clipboard" in app
    assert "URL.createObjectURL" in app


def test_portfolio_api_client_is_opt_in_and_session_scoped():
    client = read(STATIC_ROOT / "assets" / "portfolio-api.js")
    html = read(STATIC_ROOT / "index.html")
    assert 'meta name="content-api-base" content=""' in html
    assert 'src="assets/portfolio-api.js"' in html
    assert "sessionStorage" in client
    assert "localStorage" not in client
    assert '"X-Operator-Key"' in client
    assert "window.PortfolioApi" in client
    assert "http://" not in client
    assert "https://" not in client


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
