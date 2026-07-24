from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "src" / "operator_api" / "entrypoint.py"
BATCH_RUNTIME = ROOT / "src" / "operator_api" / "studio_v2_batch_runtime.py"
INDEX = ROOT / "web" / "static-creator-ui" / "index.html"
BATCH_JS = ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2-batch.js"
STUDIO_JS = ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2.js"


def test_content_state_batch_route_is_installed_and_bounded() -> None:
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    runtime = BATCH_RUNTIME.read_text(encoding="utf-8")

    assert "install_studio_v2_batch_routes" in entrypoint
    assert 'app.post("/studio-v2/content-states")' in runtime
    assert "max_length=100" in runtime
    assert "require_access(operator, AccessPermission.READ_PORTFOLIO)" in runtime
    assert "content_state(content_id) for content_id in ordered_ids" in runtime


def test_browser_batches_content_state_reads_before_router_loads() -> None:
    index = INDEX.read_text(encoding="utf-8")
    batch = BATCH_JS.read_text(encoding="utf-8")
    studio = STUDIO_JS.read_text(encoding="utf-8")

    assert index.index("studio-v2-api.js") < index.index("studio-v2-batch.js") < index.index("studio-v2.js")
    assert 'api.request("/studio-v2/content-states"' in batch
    assert "window.queueMicrotask(flush)" in batch
    assert "api.contentState = contentState" in batch
    assert "StudioApi.contentState(item.id)" in studio


def test_batching_preserves_rate_limit_instead_of_raising_it() -> None:
    settings = (ROOT / "src" / "operations" / "settings.py").read_text(encoding="utf-8")
    assert "requests_per_minute: int = Field(default=120" in settings
