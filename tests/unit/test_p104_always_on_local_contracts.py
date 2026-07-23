from __future__ import annotations

from pathlib import Path

import pytest

from src.application.generation_jobs.models import GenerationJobType
from src.operations.local_pipeline import LocalPipelineError, LocalPipelineService
from src.operations.local_worker_v2 import _parse_types

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_local_batch_is_bounded() -> None:
    assert LocalPipelineService._bounded_limit(1) == 1
    assert LocalPipelineService._bounded_limit(20) == 20
    with pytest.raises(LocalPipelineError):
        LocalPipelineService._bounded_limit(0)
    with pytest.raises(LocalPipelineError):
        LocalPipelineService._bounded_limit(21)


def test_worker_type_partition_is_explicit() -> None:
    assert _parse_types("script,narration") == {
        GenerationJobType.SCRIPT,
        GenerationJobType.NARRATION,
    }
    assert _parse_types("keyframe") == {GenerationJobType.KEYFRAME}
    with pytest.raises(Exception):
        _parse_types("publishing")


def test_supervisor_restarts_all_local_processes_without_publishers() -> None:
    script = read("scripts/windows/supervise_local_production.ps1")
    assert '"api"' in script
    assert '"text-audio-worker"' in script
    assert '"visual-worker"' in script
    assert "Ensure-ManagedProcess" in script
    assert "forcing restart" in script
    assert "supervisor-heartbeat.json" in script
    lowered = script.lower()
    assert "publish(" not in lowered
    assert "vercel deploy" not in lowered


def test_task_scheduler_starts_at_logon_and_restarts_failures() -> None:
    script = read("scripts/windows/install_local_production_service.ps1")
    assert "New-ScheduledTaskTrigger -AtLogOn" in script
    assert "-RestartCount 999" in script
    assert "-StartWhenAvailable" in script
    assert "-ExecutionTimeLimit ([TimeSpan]::Zero)" in script


def test_windows_secret_generation_supports_windows_powershell_51() -> None:
    script = read("scripts/windows/start_local_production.ps1")
    assert "RandomNumberGenerator]::Fill" not in script
    assert "RandomNumberGenerator]::Create()" in script
    assert ".GetBytes($buffer)" in script


def test_local_comfyui_workflow_is_configured_from_tracked_reviewed_file() -> None:
    env = read("config/local.env.example")
    assert "P68_COMFYUI_WORKFLOW_PATH=deploy/p68-rn-worker/workflows/sdxl-keyframe-api.json" in env
    assert (ROOT / "deploy/p68-rn-worker/workflows/sdxl-keyframe-api.json").exists()


def test_creator_studio_exposes_bounded_local_queue_controls() -> None:
    html = read("web/static-creator-ui/index.html")
    client = read("web/static-creator-ui/assets/local-pipeline-controls.js")
    assert 'id="queue-more-scripts"' in html
    assert 'id="continue-approved-local"' in html
    assert 'max="20"' in html
    assert "/local-production/enqueue-scripts" in client
    assert "/local-production/continue-approved" in client
    assert "setInterval" in client
    assert "automatic" not in html.lower() or "no automatic publishing" in html.lower()


def test_pipeline_routes_are_installed_in_runtime() -> None:
    entrypoint = read("src/operator_api/entrypoint.py")
    routes = read("src/operator_api/local_pipeline_runtime.py")
    assert "install_local_pipeline_routes" in entrypoint
    assert '@app.post("/local-production/enqueue-scripts")' in routes
    assert '@app.post("/local-production/continue-approved")' in routes
    assert "RUN_PRODUCTION" in routes


def test_no_paid_or_live_execution_is_introduced() -> None:
    inspected = "\n".join(
        read(path)
        for path in (
            "src/operations/local_pipeline.py",
            "src/operations/local_worker_v2.py",
            "src/operator_api/local_pipeline_runtime.py",
            "scripts/windows/supervise_local_production.ps1",
        )
    ).lower()
    assert "estimated_cost_usd=decimal(\"0\")" in inspected
    assert "reserved_cost_usd=decimal(\"0\")" in inspected
    assert "automatic_approval" in inspected
    assert "live_publishing" in inspected
    assert "higgsfield" not in inspected
    assert "vercel deploy" not in inspected
