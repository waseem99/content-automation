from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.application.generation_jobs.models import GenerationJobType
from src.application.local_video.comfy import ComfyUIClient
from src.application.local_video.manifest import LocalVideoManifestError, load_and_verify_manifest
from src.application.local_video.models import LocalVideoOperation, LocalVideoRequest
from src.application.local_video.workflow import LocalVideoWorkflowError, verify_workflow


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0099_p114_local_video_renderer.sql"
EXAMPLE = ROOT / "config" / "p114-local-video-manifest.example.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request(**overrides):
    value = {
        "generation_job_id": UUID("00000000-0000-0000-0000-000000000001"),
        "workflow_version_id": UUID("00000000-0000-0000-0000-000000000002"),
        "model_policy_id": UUID("00000000-0000-0000-0000-000000000003"),
        "operation": LocalVideoOperation.IMAGE_TO_VIDEO,
        "source_path": Path("/tmp/source.png"),
        "prompt": "A restrained documentary camera move",
        "seed": 42,
        "width": 1280,
        "height": 720,
        "fps": 24,
        "frame_count": 96,
        "inference_steps": 12,
    }
    value.update(overrides)
    return LocalVideoRequest(**value)


def test_generation_queue_has_explicit_local_clip_type() -> None:
    assert GenerationJobType.LOCAL_CLIP.value == "local_clip"
    assert "'local_clip'" in MIGRATION.read_text(encoding="utf-8")


def test_request_requires_absolute_media_and_operation_consistency() -> None:
    assert request().frame_count == 96
    with pytest.raises(ValidationError):
        request(source_path=Path("relative.png"))
    with pytest.raises(ValidationError):
        request(operation=LocalVideoOperation.START_END_FRAME, end_path=None)
    with pytest.raises(ValidationError):
        request(end_path=Path("/tmp/end.png"))
    with pytest.raises(ValidationError):
        request(frame_count=12, fps=24)


def test_comfyui_endpoint_is_loopback_only() -> None:
    assert ComfyUIClient("http://127.0.0.1:8188").base_url.endswith("8188")
    for value in (
        "https://example.com",
        "http://192.168.1.2:8188",
        "http://user:pass@127.0.0.1:8188",
    ):
        with pytest.raises(ValueError):
            ComfyUIClient(value)


def test_workflow_verification_fails_closed_on_hash_or_path(tmp_path: Path) -> None:
    root = tmp_path / "workflows"
    root.mkdir()
    workflow = root / "approved.json"
    workflow.write_text(json.dumps({"1": {"class_type": "Example"}}), encoding="utf-8")
    checkpoint = tmp_path / "model.safetensors"
    checkpoint.write_bytes(b"checkpoint")
    verified = verify_workflow(
        workflow_root=root,
        relative_path="approved.json",
        expected_workflow_sha256=sha256(workflow),
        checkpoint_path=checkpoint,
        expected_checkpoint_sha256=sha256(checkpoint),
    )
    assert verified.workflow_sha256 == sha256(workflow)
    with pytest.raises(LocalVideoWorkflowError, match="workflow_hash_mismatch"):
        verify_workflow(
            workflow_root=root,
            relative_path="approved.json",
            expected_workflow_sha256="0" * 64,
            checkpoint_path=checkpoint,
            expected_checkpoint_sha256=sha256(checkpoint),
        )
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(LocalVideoWorkflowError, match="workflow_path_outside_approved_root"):
        verify_workflow(
            workflow_root=root,
            relative_path="../outside.json",
            expected_workflow_sha256=sha256(outside),
            checkpoint_path=checkpoint,
            expected_checkpoint_sha256=sha256(checkpoint),
        )


def test_example_manifest_is_intentionally_disabled_and_placeholder_safe() -> None:
    document = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert document["enabled"] is False
    assert all(item["workflow_sha256"] == "REPLACE_WITH_64_HEX" for item in document["workflows"])
    with pytest.raises(LocalVideoManifestError, match="local_video_renderer_not_enabled"):
        load_and_verify_manifest(EXAMPLE, repository_root=ROOT)


def test_schema_preserves_zero_fee_and_immutable_lineage() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "external_fee_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (external_fee_usd = 0)" in source
    assert "Local video request identity is immutable" in source
    assert "Completed local video bindings are immutable" in source
    assert "DROP TABLE" not in source
    assert "TRUNCATE" not in source
