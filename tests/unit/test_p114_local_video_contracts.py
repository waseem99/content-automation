from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from src.application.generation_jobs.models import GenerationJobType
from src.application.local_video.models import LocalVideoJob, LocalVideoJobStatus, LocalVideoRequest
from src.application.local_video.provider import ComfyUILocalVideoProvider


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0099_p114_local_video_renderers.sql"
CONFIG = ROOT / "config" / "local.env.example"
WORKER = ROOT / "src" / "operations" / "local_video_worker.py"


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
        "output_prefix": "p114-video/test",
    }
    values.update(overrides)
    return LocalVideoRequest(**values)


def test_local_clip_is_distinct_from_premium_clip() -> None:
    assert GenerationJobType.LOCAL_CLIP.value == "local_clip"
    assert GenerationJobType.LOCAL_CLIP is not GenerationJobType.PREMIUM_CLIP


def test_request_is_hash_pinned_and_idempotent(tmp_path: Path) -> None:
    first = _request(tmp_path)
    second = _request(tmp_path)
    assert first.idempotency_key == second.idempotency_key
    with pytest.raises(ValueError, match="workflow_sha256"):
        _request(tmp_path, workflow_sha256="not-a-sha")


def test_provider_rejects_workflow_file_drift_before_submission(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.workflow_path.write_text("{}", encoding="utf-8")
    provider = ComfyUILocalVideoProvider(base_url="http://127.0.0.1:8188")
    with pytest.raises(RuntimeError, match="workflow hash mismatch"):
        provider.workflow_for(request)
    provider.client.close()


def test_provider_recognizes_only_video_outputs() -> None:
    video = ComfyUILocalVideoProvider._video_descriptor(
        {"outputs": {"8": {"videos": [{"filename": "clip.mp4", "type": "output"}]}}}
    )
    image = ComfyUILocalVideoProvider._video_descriptor(
        {"outputs": {"8": {"images": [{"filename": "still.png", "type": "output"}]}}}
    )
    assert video and video["filename"] == "clip.mp4"
    assert image is None


def test_terminal_job_contract_and_zero_fee_schema() -> None:
    job = LocalVideoJob(
        provider="local-comfyui-video",
        provider_job_id="prompt-1",
        idempotency_key="b" * 64,
        status=LocalVideoJobStatus.SUCCEEDED,
        model_key="Wan2.2-TI2V-5B",
        workflow_sha256="c" * 64,
        submitted_at="2026-07-29T00:00:00+00:00",
        output_descriptor={"filename": "clip.mp4"},
    )
    assert job.status == LocalVideoJobStatus.SUCCEEDED
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "'local_clip'" in migration
    assert "external_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (external_cost_usd = 0)" in migration
    assert "Terminal local video executions are immutable" in migration
    assert "DROP TABLE" not in migration
    assert "TRUNCATE" not in migration


def test_worker_and_configuration_fail_closed_by_default() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    assert "P114_LOCAL_VIDEO_ENABLED=false" in config
    assert "OPS_MIGRATION_HEAD=0099_p114_local_video_renderers.sql" in config
    assert "model-use preflight rejected" in worker
    assert "external_fee_incurred\": False" in worker
    assert "automatic_publishing\": False" in worker
    assert "GenerationJobType.LOCAL_CLIP" in worker
