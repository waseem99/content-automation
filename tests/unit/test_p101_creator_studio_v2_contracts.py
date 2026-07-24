from __future__ import annotations

import ast
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.operator_api.studio_runtime import install_studio_routes


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "web" / "static-creator-ui"
ASSETS = UI / "assets"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v2_shell_replaces_the_legacy_one_page_console() -> None:
    index = read(UI / "index.html")

    assert 'href="/app/dashboard"' in index
    assert 'id="app-view"' in index
    for asset in (
        "studio-v2-api.js",
        "studio-v2.js",
        "studio-v2-media.js",
        "studio-v2-extensions.js",
        "studio-v2-queue.js",
    ):
        assert f'src="/assets/{asset}"' in index
    assert "portfolio-api.js" not in index
    assert "production-console.js" not in index
    assert "local-pipeline-controls.js" not in index
    assert "advanced-tools" not in index
    assert "p100-console" not in index


def test_v2_application_exposes_task_oriented_routes() -> None:
    script = read(ASSETS / "studio-v2.js")
    extensions = read(ASSETS / "studio-v2-extensions.js")
    runtime = read(ROOT / "src" / "operator_api" / "studio_runtime.py")

    for route in (
        "/app/dashboard",
        "/app/content",
        "/app/content/new",
        "/app/reviews",
        "/app/team",
        "/app/settings",
        "/app/operations",
    ):
        assert route in script or route in runtime

    assert "/app/publishing" in extensions
    assert "Create content" in script
    assert "Review inbox" in script
    assert "Start local production" in script
    assert "MP4 preview" in script
    assert "Release & delivery" in extensions


def test_normal_workflow_has_no_prompt_uuid_or_json_editor() -> None:
    inspected = "\n".join(
        read(ASSETS / name)
        for name in (
            "studio-v2.js",
            "studio-v2-media.js",
            "studio-v2-extensions.js",
            "studio-v2-queue.js",
        )
    )
    index = read(UI / "index.html")

    assert "window.prompt" not in inspected
    assert "Draft monthly plan UUID" not in inspected
    assert "JSON.stringify" not in index
    assert "json-textarea" not in inspected
    assert "Advanced production tools" not in index


def test_v2_api_client_covers_the_golden_path() -> None:
    client = read(ASSETS / "studio-v2-api.js")

    for contract in (
        "createContent:",
        "generateScript:",
        "submitScript:",
        "decideScript:",
        "startLocalProduction:",
        "selectAudioTake:",
        "buildLocalAudioMix:",
        "submitAudio:",
        "decideAudio:",
        "submitVisualProject:",
        "decideVisualProject:",
        "authenticatedMediaUrl:",
        "jobMediaUrl:",
        "teamKeys:",
        "enqueueLocalScripts:",
        "continueApproved:",
    ):
        assert contract in client


def test_v2_completion_extensions_cover_suggestions_publisher_p100_and_queue() -> None:
    source = read(ASSETS / "studio-v2-extensions.js")
    queue = read(ASSETS / "studio-v2-queue.js")

    assert "Generate 6 suggestions" in source
    assert "Use this idea" in source
    assert "Use an existing approved plan item" in source
    assert "Release & delivery" in source
    assert "/acceptance/pilots/bootstrap-draft" in source
    assert "/start-readiness" in source
    assert "/start-controlled" in source
    assert "The four pilot items must be unique" in source
    assert "live_delivery_evidence_required" in source
    assert 'id="queue-more-scripts"' in queue
    assert 'id="continue-approved-local"' in queue
    assert 'max="20"' in queue
    assert "include_previews: true" in queue


def test_v2_backend_is_a_thin_orchestrator_over_existing_services() -> None:
    source = read(ROOT / "src" / "operator_api" / "studio_v2_runtime.py")

    assert "PortfolioService" in source
    assert "ProductionWorkflowService" in source
    assert "GenerationJobService" in source
    assert "AudioProductionService" in source
    assert "ValidatedVisualProjectService" in source
    assert '@app.post("/studio-v2/content")' in source
    assert '@app.get("/studio-v2/content/{content_id}/state")' in source
    assert '@app.post("/studio-v2/content/{content_id}/generate-script")' in source
    assert '@app.post("/studio-v2/content/{content_id}/start-local-production")' in source
    assert "manual_brief_accepted" in source
    assert '"automatic_approval": False' in source
    assert '"live_publishing": False' in source


def test_schema_safe_content_reader_uses_existing_script_columns() -> None:
    source = read(ROOT / "src" / "operator_api" / "studio_v2_schema_patch.py")
    entrypoint = read(ROOT / "src" / "operator_api" / "entrypoint.py")
    claims_fragment = source.split("script_claims", 1)[1].split("script_sources", 1)[0]
    sources_fragment = source.split("script_sources", 1)[1].split("audio_productions", 1)[0]

    assert "ORDER BY sequence,id" in source
    assert "ORDER BY claim_key,id" in claims_fragment
    assert "ORDER BY sequence,id" not in claims_fragment
    assert "ORDER BY source_key,id" in sources_fragment
    assert "ORDER BY created_at,id" not in sources_fragment
    assert "apply_studio_v2_schema_patch()" in entrypoint


def test_guided_brief_fields_reach_the_local_script_context_and_request() -> None:
    source = read(ROOT / "src" / "operator_api" / "studio_v2_schema_patch.py")

    assert 'brief.get("platform")' in source
    assert 'brief.get("language")' in source
    assert 'brief.get("duration_seconds")' in source
    assert 'brief.get("objective")' in source
    assert 'brief.get("audience")' in source
    assert 'brief.get("notes")' in source
    assert 'context["concept"]' in source
    assert 'context["audience"]' in source
    assert '"brief_fields_applied": True' in source


def test_local_media_endpoint_is_authenticated_and_root_bounded() -> None:
    source = read(ROOT / "src" / "operator_api" / "studio_v2_media_runtime.py")

    assert "OperatorIdentity = Depends(authenticate)" in source
    assert "require_access(" in source
    assert "AccessPermission.READ_PORTFOLIO" in source
    assert "artifact_root not in candidate.parents" in source
    assert 'media_type.startswith(("audio/", "image/", "video/"))' in source
    assert 'Cache-Control"] = "private, no-store"' in source
    assert 'build-local-mix' in source
    assert 'mix-media' in source


def test_new_python_and_javascript_sources_are_syntax_valid() -> None:
    for path in (
        ROOT / "src" / "operator_api" / "studio_v2_runtime.py",
        ROOT / "src" / "operator_api" / "studio_v2_media_runtime.py",
        ROOT / "src" / "operator_api" / "studio_v2_schema_patch.py",
        ROOT / "src" / "operator_api" / "entrypoint.py",
        ROOT / "src" / "operator_api" / "studio_runtime.py",
        ROOT / "src" / "operations" / "local_audio_alignment_patch.py",
        ROOT / "src" / "operations" / "local_worker_aligned.py",
    ):
        ast.parse(read(path), filename=str(path))

    for path in (
        ASSETS / "studio-v2-api.js",
        ASSETS / "studio-v2.js",
        ASSETS / "studio-v2-media.js",
        ASSETS / "studio-v2-extensions.js",
        ASSETS / "studio-v2-queue.js",
    ):
        source = read(path)
        assert source.startswith("(() => {")
        assert source.rstrip().endswith("})();")


def test_nested_application_routes_return_the_same_shell(tmp_path: Path) -> None:
    root = tmp_path / "studio"
    (root / "assets").mkdir(parents=True)
    index = root / "index.html"
    index.write_text("<!doctype html><title>Studio v2</title>", encoding="utf-8")

    app = FastAPI()
    install_studio_routes(app, studio_root=root)
    client = TestClient(app)

    assert client.get("/").status_code == 200
    assert client.get("/app/dashboard").status_code == 200
    assert client.get("/app/content/new").status_code == 200
    assert client.get("/app/content/00000000-0000-0000-0000-000000000001/script").status_code == 200
    assert client.get("/app/publishing").status_code == 200
    status = client.get("/studio/status").json()
    assert status["kind"] == "production_creator_studio_v2"
    assert status["demo_fallback"] is False
