from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "web" / "static-creator-ui"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_production_studio_is_same_origin_routed_and_has_no_demo_fallback() -> None:
    index = read("web/static-creator-ui/index.html")
    api = read("web/static-creator-ui/assets/studio-v2-api.js")
    core = read("web/static-creator-ui/assets/studio-v2.js")

    assert 'href="/app/dashboard"' in index
    assert 'id="app-view"' in index
    assert 'id="login-dialog"' in index
    assert 'id="operator-key"' in index
    assert 'src="/assets/studio-v2-api.js"' in index
    assert "Demo data" not in index + api + core
    assert "portfolio-api.js" not in index
    assert "production-console.js" not in index
    assert "window.prompt" not in api + core
    assert "sessionStorage" in api
    assert "sameOrigin()" in api


def test_local_compose_exposes_only_postgres_on_loopback() -> None:
    compose = yaml.safe_load(read("compose.local.yml"))
    postgres = compose["services"]["postgres"]
    assert postgres["ports"] == ["127.0.0.1:${POSTGRES_PORT:-5434}:5432"]
    assert "ngrok" not in compose["services"]
    assert "ollama" not in compose["services"]
    assert "comfyui" not in compose["services"]


def test_windows_launchers_start_aligned_workers_and_optional_ngrok() -> None:
    manual = read("scripts/windows/start_local_production.ps1")
    supervisor = read("scripts/windows/supervise_local_production.ps1")

    assert "src.operator_api.entrypoint:app" in manual + supervisor
    assert "src.operations.local_worker_aligned" in manual
    assert manual.count("src.operations.local_worker_v2") == 0
    assert supervisor.count("src.operations.local_worker_aligned") == 3
    assert "src.operations.local_onboarding_v2" in manual + supervisor
    assert "src.infrastructure.database.cli" in manual + supervisor
    assert 'Start-Process -FilePath "ngrok"' in manual
    assert 'New-ManagedState "ngrok" "ngrok"' in supervisor
    assert "vercel" not in (manual + supervisor).lower()
    assert "no managed renderer or live publishing is enabled" in manual.lower()


def test_alignment_is_local_optional_and_managed_render_stays_disabled_by_default() -> None:
    patch = read("src/operations/local_audio_alignment_patch.py")
    wrapper = read("src/operations/local_worker_aligned.py")
    requirements = read("video-engine/voice-requirements.txt")
    env = read("config/local.env.example")

    assert "faster-whisper" in requirements
    assert "from faster_whisper import WhisperModel" in patch
    assert "proportional_preview_fallback" in patch
    assert '"final_approval_allowed": False' in patch
    assert "validate_forced_alignment" in patch
    assert "apply_local_audio_alignment_patch()" in wrapper
    assert "LOCAL_ALIGNMENT_ENABLED=true" in env
    assert "LOCAL_ALIGNMENT_DEVICE=cpu" in env
    assert "HIGGSFIELD_ENABLED=false" in env
    assert "HIGGSFIELD_CLI_PATH=higgsfield" in env
    assert "HIGGSFIELD_WORKER_OPERATOR_ID=higgsfield-worker" in env


def test_routed_studio_keeps_role_specific_work_separate() -> None:
    core = read("web/static-creator-ui/assets/studio-v2.js")
    extensions = read("web/static-creator-ui/assets/studio-v2-extensions.js")
    queue = read("web/static-creator-ui/assets/studio-v2-queue.js")

    assert 'show: hasRole("producer")' in core
    assert 'show: hasRole("reviewer")' in core
    assert 'show: isAdmin()' in core
    assert 'hasRole("publisher")' in extensions
    assert 'window.location.pathname === "/app/publishing"' in extensions
    assert 'id="queue-more-scripts"' in queue
    assert 'id="continue-approved-local"' in queue
    assert 'max="20"' in queue
    assert "include_previews: true" in queue


def test_readme_routes_new_work_through_creator_studio() -> None:
    readme = read("README.md")
    assert "P84–P107" in readme
    assert "/app/dashboard" in readme
    assert "start_local_production.ps1" in readme
    assert "LOCAL_PRODUCTION_RUNBOOK.md" in readme
    assert "automatic public publishing" in readme.lower()


def test_runtime_entrypoint_serves_studio_without_replacing_canonical_factory() -> None:
    entrypoint = read("src/operator_api/entrypoint.py")
    factory = read("src/operator_api/runtime_factory.py")
    assert "install_studio_routes(application)" in entrypoint
    assert "install_studio_v2_routes" in entrypoint
    assert "install_studio_v2_media_routes" in entrypoint
    assert "create_configured_app" in entrypoint
    assert "install_acceptance_controlled_start_routes" in factory
