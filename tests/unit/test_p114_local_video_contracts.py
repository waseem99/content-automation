from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from src.application.generation_jobs.models import GenerationJobType
from src.application.local_video.models import LocalVideoJob, LocalVideoJobStatus, LocalVideoRequest
from src.application.local_video.provider import ComfyUILocalVideoProvider


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0099_p114_local_video_renderers.sql"
CONFIG = ROOT / "config" / "local.env.example"
WORKER = ROOT / "src" / "operations" / "local_video_worker.py"
ONBOARDING = ROOT / "src" / "operations" / "local_onboarding_v2.py"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(tmp_path: Path, **overrides) -> LocalVideoRequest:
    workflow = tmp_path / "workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {
                    "inputs": {
                        "prompt": "{{POSITIVE_PROMPT}}",
                        "seed": "{{SEED}}",
                        "frames": "{{FRAME_COUNT}}",
                    },
                    "class_type": "P114ContractNode",
                }
            }
        ),
        encoding="utf-8",
    )
    image = tmp_path / "input.png"
    image.write_bytes(b"not-a-real-image-but-stable-contract-fixture")
    values = {
        "generation_job_id": UUID("00000000-0000-0000-0000-000000000001"),
        "generation_attempt_id": UUID("00000000-0000-0000-0000-000000000002"),
        "pilot_case_id": None,
        "provider_key": "wan-ai",
        "model_key": "Wan2.2-TI2V-5B",
        "workflow_key": "wan-i2v-draft",
        "workflow_path": workflow,
        "workflow_sha256": _digest(workflow),
        "checkpoint_sha256": "a" * 64,
        "input_image_path": image,
        "end_image_path": None,
        "prompt": "A controlled slow push toward the approved subject.",
        "negative_prompt": "warped anatomy, text, watermark",
        "seed": 42,
        "width": 1280,
        "height": 720,
        "fps": 24,
        "frame_count": 96,
        "inference_steps": 12,
        "output_prefix": "p114-video/test/attempt-1",
    }
    values.update(overrides)
    return LocalVideoRequest(**values)


def _job(status: LocalVideoJobStatus = LocalVideoJobStatus.RUNNING) -> LocalVideoJob:
    return LocalVideoJob(
        provider="local-comfyui-video",
        provider_job_id="prompt-1",
        idempotency_key="b" * 64,
        status=status,
        model_key="Wan2.2-TI2V-5B",
        workflow_sha256="c" * 64,
        submitted_at="2026-07-29T00:00:00+00:00",
        output_descriptor={"filename": "clip.mp4"} if status == LocalVideoJobStatus.SUCCEEDED else None,
    )


def test_local_clip_is_distinct_from_premium_clip() -> None:
    assert GenerationJobType.LOCAL_CLIP.value == "local_clip"
    assert GenerationJobType.LOCAL_CLIP is not GenerationJobType.PREMIUM_CLIP


def test_request_is_hash_pinned_idempotent_and_attempt_specific(tmp_path: Path) -> None:
    first = _request(tmp_path)
    second = _request(tmp_path)
    retry = _request(
        tmp_path,
        generation_attempt_id=UUID("00000000-0000-0000-0000-000000000003"),
        output_prefix="p114-video/test/attempt-2",
    )
    assert first.idempotency_key == second.idempotency_key
    assert first.idempotency_key != retry.idempotency_key
    with pytest.raises(ValueError, match="workflow_sha256"):
        _request(tmp_path, workflow_sha256="not-a-sha")


def test_provider_rejects_workflow_file_drift_before_submission(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.workflow_path.write_text("{}", encoding="utf-8")
    provider = ComfyUILocalVideoProvider(base_url="http://127.0.0.1:8188")
    with pytest.raises(RuntimeError, match="workflow hash mismatch"):
        provider.workflow_for(request)
    provider.client.close()


def test_provider_is_loopback_only() -> None:
    for endpoint in (
        "https://example.com",
        "http://user:password@127.0.0.1:8188",
        "http://127.0.0.1:8188/api",
        "http://127.0.0.1:8188?token=secret",
    ):
        with pytest.raises(ValueError, match="local ComfyUI"):
            ComfyUILocalVideoProvider(base_url=endpoint)


def test_provider_cancels_only_the_named_queued_prompt() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    client = httpx.Client(
        base_url="http://127.0.0.1:8188",
        transport=httpx.MockTransport(handler),
        trust_env=False,
    )
    provider = ComfyUILocalVideoProvider(base_url="http://127.0.0.1:8188", client=client)
    cancelled = provider.cancel(_job())
    assert cancelled.status == LocalVideoJobStatus.CANCELLED
    assert len(requests) == 1
    assert requests[0].url.path == "/queue"
    assert json.loads(requests[0].content) == {"delete": ["prompt-1"]}
    assert "/interrupt" not in requests[0].url.path
    client.close()


def test_provider_streams_only_canonical_mp4(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/view"
        return httpx.Response(200, headers={"content-type": "video/mp4"}, content=b"mp4-bytes")

    client = httpx.Client(
        base_url="http://127.0.0.1:8188",
        transport=httpx.MockTransport(handler),
        trust_env=False,
    )
    provider = ComfyUILocalVideoProvider(base_url="http://127.0.0.1:8188", client=client)
    output = provider.download(_job(LocalVideoJobStatus.SUCCEEDED), tmp_path / "clip.mp4")
    assert output.read_bytes() == b"mp4-bytes"
    client.close()


def test_provider_recognizes_only_mp4_outputs() -> None:
    video = ComfyUILocalVideoProvider._video_descriptor(
        {"outputs": {"8": {"videos": [{"filename": "clip.mp4", "type": "output"}]}}}
    )
    webm = ComfyUILocalVideoProvider._video_descriptor(
        {"outputs": {"8": {"videos": [{"filename": "clip.webm", "type": "output"}]}}}
    )
    image = ComfyUILocalVideoProvider._video_descriptor(
        {"outputs": {"8": {"images": [{"filename": "still.png", "type": "output"}]}}}
    )
    assert video and video["filename"] == "clip.mp4"
    assert webm is None
    assert image is None


def test_terminal_job_contract_and_zero_fee_retry_schema() -> None:
    job = _job(LocalVideoJobStatus.SUCCEEDED)
    assert job.status == LocalVideoJobStatus.SUCCEEDED
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "'local_clip'" in migration
    assert "generation_attempt_id uuid NOT NULL UNIQUE" in migration
    assert "local_video_executions_job_idx" in migration
    assert "external_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (external_cost_usd = 0)" in migration
    assert "Terminal local video executions are immutable" in migration
    assert "BEFORE UPDATE OR DELETE ON football_brief.local_video_executions" in migration
    assert "DROP TABLE" not in migration
    assert "TRUNCATE" not in migration


def test_active_workflow_requires_catalogue_binding_and_is_immutable() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "renderer_catalogue_entry_id IS NOT NULL" in migration
    assert "protect_local_video_workflow" in migration
    assert "Active local video workflows may only be retired without changing lineage" in migration
    assert "BEFORE UPDATE OR DELETE ON football_brief.local_video_workflows" in migration


def test_worker_and_configuration_fail_closed_by_default() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    onboarding = ONBOARDING.read_text(encoding="utf-8")
    assert "P114_LOCAL_VIDEO_ENABLED=false" in config
    assert "P114_WORKFLOW_ROOT=config/local-video-workflows" in config
    assert "OPS_MIGRATION_HEAD=0108_p131_staged_acceptance_closeout.sql" in config
    assert 'os.getenv("P114_LOCAL_VIDEO_ENABLED", "false")' in worker
    assert "P114 local video worker is disabled" in worker
    assert "outside the approved workflow root" in worker
    assert "active P93 renderer catalogue entry is required" in worker
    assert "P93 renderer commercial-use evidence is required" in worker
    assert "P93 renderer must declare MP4 output support" in worker
    assert "requested resolution is not approved" in worker
    assert "requested duration is outside" in worker
    assert "approved input keyframe image asset is required" in worker
    assert "model-use preflight rejected" in worker
    assert "generation_attempt_id=%s" in worker
    assert '"generation_attempt_id": str(attempt["id"])' in worker
    assert '"attempts"' in worker
    assert "provider_request_id=None" in worker
    assert "_bind_provider_request" in worker
    assert worker.index("self._record_execution(") < worker.index("self.provider.health()")
    assert "'internal_only'" in worker
    assert '"review_status": "pending"' in worker
    assert '"external_fee_incurred": False' in worker
    assert '"automatic_publishing": False' in worker
    assert "GenerationJobType.LOCAL_CLIP" in worker
    assert '"LOCAL_VIDEO_WORKER_OPERATOR_ID", "local-video-worker"' in onboarding
    assert '"api_key_created": False' in onboarding
