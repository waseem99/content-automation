from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "web" / "static-creator-ui"
ASSETS = UI / "assets"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_controlled_snapshot_routes_are_registered_on_the_configured_app() -> None:
    runtime = read(ROOT / "src" / "operator_api" / "acceptance_controlled_snapshot_runtime.py")
    factory = read(ROOT / "src" / "operator_api" / "runtime_factory.py")

    assert '@app.get("/acceptance/pilots/{pilot_id}/evidence-preview")' in runtime
    assert '@app.post("/acceptance/pilots/{pilot_id}/snapshot-evidence")' in runtime
    assert "acceptance_snapshot_role_required" in runtime
    assert "pilot_brand_scope_required" in runtime
    assert "install_acceptance_controlled_snapshot_routes" in factory


def test_creator_studio_exposes_fail_closed_snapshot_continuation() -> None:
    index = read(UI / "index.html")
    source = read(ASSETS / "studio-v2-p100-snapshot.js")

    assert 'src="/assets/studio-v2-p100-snapshot.js"' in index
    assert index.index('src="/assets/studio-v2-extensions.js"') < index.index(
        'src="/assets/studio-v2-p100-snapshot.js"'
    )
    assert "/evidence-preview" in source
    assert "/snapshot-evidence" in source
    assert "snapshot_ready" in source
    assert "controlled_start_event_sha256" in source
    assert "bootstrap_request_sha256" in source
    assert "runbook_sha256" in source
    assert "snapshot_sha256" in source
    assert "started_at" in source
    assert "No pass/fail values or hashes are entered manually." in source
    assert 'type="text"' not in source
    assert 'type="password"' not in source
    assert "window.prompt" not in source
    assert "automatic" not in source.lower()


def test_snapshot_python_and_javascript_sources_are_syntax_valid() -> None:
    for path in (
        ROOT / "src" / "application" / "acceptance" / "controlled_snapshot_models.py",
        ROOT / "src" / "application" / "acceptance" / "controlled_snapshot_service.py",
        ROOT / "src" / "operator_api" / "acceptance_controlled_snapshot_runtime.py",
    ):
        ast.parse(read(path), filename=str(path))

    source = read(ASSETS / "studio-v2-p100-snapshot.js")
    assert source.startswith("(() => {")
    assert source.rstrip().endswith("})();")
