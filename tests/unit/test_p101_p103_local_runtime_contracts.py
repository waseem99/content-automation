from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_production_studio_is_same_origin_and_has_no_demo_fallback() -> None:
    index = (ROOT / "web/static-creator-ui/index.html").read_text(encoding="utf-8")
    api = (ROOT / "web/static-creator-ui/assets/portfolio-api.js").read_text(encoding="utf-8")
    console = (ROOT / "web/static-creator-ui/assets/production-console.js").read_text(encoding="utf-8")
    compat = (ROOT / "web/static-creator-ui/assets/p100-api-compat.js").read_text(encoding="utf-8")
    assert 'content-api-mode" content="same-origin"' in index
    assert "Demo data" not in index
    assert "Operator API URL" not in index + api + console
    assert "sessionStorage" in api
    assert "operator-key" in index
    assert "no automatic publishing" in index.lower()
    assert 'id="script-review-dialog"' in index
    assert 'id="advanced-tools"' in index
    assert "data-open-script" in console
    assert 'adapter_mode: "local_model"' in console
    assert "Generate with local model" in console
    assert "/start-controlled" in compat
    assert "ready_to_start" in compat


def test_local_compose_exposes_only_postgres_on_loopback() -> None:
    compose = yaml.safe_load((ROOT / "compose.local.yml").read_text(encoding="utf-8"))
    postgres = compose["services"]["postgres"]
    assert postgres["ports"] == ["127.0.0.1:${POSTGRES_PORT:-5434}:5432"]
    assert "ngrok" not in compose["services"]
    assert "ollama" not in compose["services"]
    assert "comfyui" not in compose["services"]


def test_windows_launcher_starts_api_worker_and_optional_ngrok() -> None:
    script = (ROOT / "scripts/windows/start_local_production.ps1").read_text(encoding="utf-8")
    assert "src.operator_api.entrypoint:app" in script
    assert "src.operations.local_worker" in script
    assert "src.operations.local_onboarding" in script
    assert "src.infrastructure.database.cli migrate" in script
    assert 'ngrok" -ArgumentList @("http"' in script
    assert "vercel" not in script.lower()
    assert "no managed renderer or live publishing is enabled" in script.lower()
    assert "System.Collections.IDictionary" in script
    assert '$keys[(New-Secret)]' in script


def test_worker_is_local_only_and_human_reviewed() -> None:
    worker = (ROOT / "src/operations/local_worker.py").read_text(encoding="utf-8")
    assert "SUPPORTED_TYPES = {GenerationJobType.NARRATION, GenerationJobType.KEYFRAME}" in worker
    assert "external_fee_incurred" in worker
    assert "automatic_approval" in worker
    assert "CandidateCheckStatus.WARNING" in worker
    assert "GenerationJobType.PUBLISHING" not in worker


def test_local_env_keeps_managed_renderer_unconfigured() -> None:
    env = (ROOT / "config/local.env.example").read_text(encoding="utf-8")
    assert "OPERATOR_API_KEYS_JSON={}" in env
    assert "OPS_MIGRATION_HEAD=0090_acceptance_start_actor.sql" in env
    assert "HIGGSFIELD" not in env
    assert "P68_COMFYUI_BASE_URL=http://127.0.0.1:8188" in env


def test_readme_routes_new_work_through_creator_studio() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "P84–P100" in readme
    assert "start_local_production.ps1" in readme
    assert "LOCAL_PRODUCTION_RUNBOOK.md" in readme
    assert "Automatic live publishing" in readme


def test_runtime_entrypoint_serves_studio_without_replacing_canonical_factory() -> None:
    entrypoint = (ROOT / "src/operator_api/entrypoint.py").read_text(encoding="utf-8")
    factory = (ROOT / "src/operator_api/runtime_factory.py")
    assert "install_studio_routes(application)" in entrypoint
    assert "create_configured_app" in entrypoint
    assert not factory.exists() or "acceptance_controlled_start" not in entrypoint
