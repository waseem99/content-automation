from __future__ import annotations

from pathlib import Path

import pytest

from src.application.generation_jobs.models import GenerationJobType
from src.operations.always_on_pipeline import AlwaysOnLocalPipelineService
from src.operations.local_pipeline import LocalPipelineError
from src.operations.local_worker_v2 import _parse_types

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_local_batch_is_bounded() -> None:
    assert AlwaysOnLocalPipelineService._bounded_limit(1) == 1
    assert AlwaysOnLocalPipelineService._bounded_limit(20) == 20
    with pytest.raises(LocalPipelineError):
        AlwaysOnLocalPipelineService._bounded_limit(0)
    with pytest.raises(LocalPipelineError):
        AlwaysOnLocalPipelineService._bounded_limit(21)


def test_worker_type_partition_is_explicit() -> None:
    assert _parse_types("script,narration") == {
        GenerationJobType.SCRIPT,
        GenerationJobType.NARRATION,
    }
    assert _parse_types("keyframe") == {GenerationJobType.KEYFRAME}
    assert _parse_types("preview") == {GenerationJobType.PREVIEW}
    with pytest.raises(Exception):
        _parse_types("publishing")


def test_supervisor_restarts_all_local_processes_without_publishers() -> None:
    script = read("scripts/windows/supervise_local_production.ps1")
    wrapper = read("scripts/windows/supervise_always_on_local_production.ps1")
    continuation = read("src/operations/always_on_continuation.py")
    assert '"api"' in script
    assert '"text-audio-worker"' in script
    assert '"visual-worker"' in script
    assert '"preview-worker"' in script
    assert '"--job-types", "preview"' in script
    assert "Ensure-ManagedProcess" in script
    assert "forcing restart" in script
    assert "supervisor-heartbeat.json" in script
    assert "always_on_continuation" in wrapper
    assert "continuation.error.log" in wrapper
    assert "AlwaysOnLocalPipelineService" in continuation
    lowered = "\n".join((script, wrapper, continuation)).lower()
    assert "publish(" not in lowered
    assert "vercel deploy" not in lowered


def test_task_scheduler_starts_at_logon_and_restarts_failures() -> None:
    script = read("scripts/windows/install_local_production_service.ps1")
    assert "supervise_always_on_local_production.ps1" in script
    assert "New-ScheduledTaskTrigger -AtLogOn" in script
    assert "-RestartCount 999" in script
    assert "-StartWhenAvailable" in script
    assert "-ExecutionTimeLimit ([TimeSpan]::Zero)" in script


def test_windows_secret_generation_supports_windows_powershell_51() -> None:
    script = read("scripts/windows/start_local_production.ps1")
    assert "RandomNumberGenerator]::Fill" not in script
    assert "RandomNumberGenerator]::Create()" in script
    assert ".GetBytes($buffer)" in script


def test_local_comfyui_and_ffmpeg_are_explicitly_configured() -> None:
    env = read("config/local.env.example")
    launcher = read("scripts/windows/start_local_production.ps1")
    assert "P68_COMFYUI_WORKFLOW_PATH=deploy/p68-rn-worker/workflows/sdxl-keyframe-api.json" in env
    assert (ROOT / "deploy/p68-rn-worker/workflows/sdxl-keyframe-api.json").exists()
    assert "PORTFOLIO_MEDIA_ROOT=.runtime/artifacts" in env
    assert "LOCAL_FFMPEG_PATH=ffmpeg" in env
    assert "Gyan.FFmpeg" in launcher


def test_creator_studio_exposes_bounded_local_queue_controls() -> None:
    html = read("web/static-creator-ui/index.html")
    client = read("web/static-creator-ui/assets/local-pipeline-controls.js")
    assert 'id="queue-more-scripts"' in html
    assert 'id="continue-approved-local"' in html
    assert 'max="20"' in html
    assert "/local-production/enqueue-scripts" in client
    assert "/local-production/continue-approved" in client
    assert "include_previews: true" in client
    assert "MP4 preview" in client
    assert "setInterval" in client
    assert "automatic" not in html.lower() or "no automatic publishing" in html.lower()


def test_pipeline_routes_are_installed_with_pinned_lineage_service() -> None:
    entrypoint = read("src/operator_api/entrypoint.py")
    routes = read("src/operator_api/local_pipeline_runtime.py")
    pipeline = read("src/operations/always_on_pipeline.py")
    assert "install_local_pipeline_routes" in entrypoint
    assert "AlwaysOnLocalPipelineService" in routes
    assert '@app.post("/local-production/enqueue-scripts")' in routes
    assert '@app.post("/local-production/continue-approved")' in routes
    assert "include_previews" in routes
    assert "RUN_PRODUCTION" in routes
    assert "production_workflow_versions" in pipeline
    assert '"script_version_id": str(row["script_version_id"])' in pipeline


def test_ffmpeg_preview_is_safe_zero_fee_and_reviewable() -> None:
    worker = read("src/operations/local_worker_v2.py")
    pipeline = read("src/operations/always_on_pipeline.py")
    assert "GenerationJobType.PREVIEW" in worker
    assert "ffmpeg-local" in pipeline
    assert "subprocess.run(" in worker
    assert "shell=False" in worker
    assert "capture_output=True" in worker
    assert '"human_review_required": True' in worker
    assert "portfolio_content_artifacts" in worker
    assert "'preview'" in worker
    assert "lifecycle_status,original_filename" in worker
    assert "'approved'" in worker


def test_no_paid_or_live_execution_is_introduced() -> None:
    inspected = "\n".join(
        read(path)
        for path in (
            "src/operations/local_pipeline.py",
            "src/operations/always_on_pipeline.py",
            "src/operations/always_on_continuation.py",
            "src/operations/local_worker_v2.py",
            "src/operator_api/local_pipeline_runtime.py",
            "scripts/windows/supervise_local_production.ps1",
            "scripts/windows/supervise_always_on_local_production.ps1",
        )
    ).lower()
    assert "estimated_cost_usd=decimal(\"0\")" in inspected
    assert "reserved_cost_usd=decimal(\"0\")" in inspected
    assert "automatic_approval" in inspected
    assert "live_publishing" in inspected
    assert "higgsfield" not in inspected
    assert "vercel deploy" not in inspected
