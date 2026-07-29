from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.application.generation_jobs.models import GenerationJobType
from src.application.local_video.models import LocalVideoEnqueueRequest
from src.p114_video_provider import ComfyUIVideoProvider, LocalVideoGenerationRequest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "deploy/p114-local-video/workflows/wan2.2-ti2v-5b-i2v-api.json"
HUNYUAN = ROOT / "deploy/p114-local-video/hunyuan-video-1.5-reference.json"
MIGRATIONS = [
    ROOT / "migrations/0099_p114_dual_local_video_renderer.sql",
    ROOT / "migrations/0100_p114_pilot_attempt_binding.sql",
]
ONBOARDING = ROOT / "src/operations/p114_renderer_onboarding.py"
WORKER = ROOT / "src/operations/p114_local_video_worker.py"
RUNTIME = ROOT / "src/operator_api/local_video_runtime.py"
FACTORY = ROOT / "src/operator_api/runtime_factory.py"
CONFIG = ROOT / "config/local.env.example"
DEPLOY = ROOT / "scripts/windows/deploy_remote_content_automation.ps1"
SUPERVISOR = ROOT / "scripts/windows/supervise_always_on_local_production.ps1"
SETUP = ROOT / "scripts/windows/setup_p114_wan_renderer.ps1"


def request_payload(**overrides):
    value = {
        "portfolio_content_id": "00000000-0000-0000-0000-000000000001",
        "content_version": 1,
        "input_asset_id": "00000000-0000-0000-0000-000000000002",
        "provider_key": "wan-ai",
        "model_key": "Wan2.2-TI2V-5B",
        "distribution_scope": "global_public",
        "prompt": "A slow controlled camera push toward a wildlife subject.",
        "duration_seconds": 5,
        "width": 1280,
        "height": 704,
        "fps": 24,
        "seed": 42,
        "inference_steps": 20,
        "idempotency_key": "p114:test:clip:0001",
    }
    value.update(overrides)
    return value


def test_local_clip_job_type_is_part_of_existing_p87_queue() -> None:
    assert GenerationJobType.LOCAL_CLIP.value == "local_clip"
    assert GenerationJobType.LOCAL_CLIP in set(GenerationJobType)


def test_local_video_contract_is_bounded_and_derives_frames() -> None:
    request = LocalVideoEnqueueRequest(**request_payload())
    assert request.frame_count == 121
    assert request.max_attempts == 2
    for duration in (2, 7):
        with pytest.raises(ValidationError):
            LocalVideoEnqueueRequest(**request_payload(duration_seconds=duration))
    with pytest.raises(ValidationError):
        LocalVideoEnqueueRequest(
            **request_payload(distribution_scope="territory_limited", release_territories=[])
        )


def test_wan_workflow_is_api_format_and_uses_reviewed_native_nodes(tmp_path: Path) -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    assert workflow
    assert all(isinstance(node, dict) and node.get("class_type") for node in workflow.values())
    classes = {node["class_type"] for node in workflow.values()}
    assert {
        "UNETLoader",
        "CLIPLoader",
        "VAELoader",
        "Wan22ImageToVideoLatent",
        "KSampler",
        "CreateVideo",
        "SaveVideo",
    } <= classes
    assert "wan2.2_ti2v_5B_fp16.safetensors" in WORKFLOW.read_text(encoding="utf-8")
    assert "umt5_xxl_fp8_e4m3fn_scaled.safetensors" in WORKFLOW.read_text(encoding="utf-8")
    assert "wan2.2_vae.safetensors" in WORKFLOW.read_text(encoding="utf-8")

    image = tmp_path / "input.png"
    image.write_bytes(b"not-used-by-workflow-render")
    digest = hashlib.sha256(WORKFLOW.read_bytes()).hexdigest()

    class NoNetworkClient:
        pass

    provider = ComfyUIVideoProvider(
        base_url="http://127.0.0.1:8188",
        workflow_path=WORKFLOW,
        expected_workflow_sha256=digest,
        client=NoNetworkClient(),
    )
    rendered = provider.workflow_for(
        LocalVideoGenerationRequest(
            job_id="job",
            prompt="positive",
            negative_prompt="negative",
            seed=1,
            width=1280,
            height=704,
            frame_count=121,
            fps=24,
            inference_steps=20,
            cfg=5.0,
            sampler_name="uni_pc",
            scheduler="simple",
            input_image=image,
            output_prefix="p114/job/clip",
            model_key="Wan2.2-TI2V-5B",
        ),
        uploaded_image="p114-input.png",
    )
    serialized = json.dumps(rendered)
    assert "{{" not in serialized
    assert "positive" in serialized
    assert "p114-input.png" in serialized


def test_provider_detects_only_downloadable_video_outputs() -> None:
    descriptor = ComfyUIVideoProvider._find_video_descriptor(
        {
            "12": {
                "images": [{"filename": "preview.png"}],
                "videos": [{"filename": "clip.mp4", "subfolder": "p114", "type": "output"}],
            }
        }
    )
    assert descriptor and descriptor["filename"] == "clip.mp4"
    assert ComfyUIVideoProvider._find_video_descriptor({"1": {"images": [{"filename": "still.png"}]}}) is None


def test_hunyuan_reference_is_fail_closed() -> None:
    reference = json.loads(HUNYUAN.read_text(encoding="utf-8"))
    assert reference["execution_enabled"] is False
    assert reference["automatic_download"] is False
    assert reference["automatic_activation"] is False
    assert reference["automatic_public_distribution"] is False
    assert "territory-cleared child policy" in reference["blocked_reason"]


def test_schema_is_forward_only_and_preserves_exact_lineage() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)
    assert "DROP TABLE" not in source
    assert "TRUNCATE" not in source
    assert "local_clip" in source
    assert "local_video_renderer_profiles" in source
    assert "local_video_clip_bindings" in source
    assert "workflow_sha256" in source
    assert "model_evidence" in source
    assert "Local video clip lineage is immutable" in source
    assert "create_p114_pilot_attempt" in source
    assert "generation_job_id" in source
    assert "checkpoint_sha256" in source


def test_onboarding_and_setup_are_explicit_and_do_not_download_models() -> None:
    onboarding = ONBOARDING.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    assert 'P114_LOCAL_VIDEO_ENABLED=false' in config
    assert 'P114_WAN_EXECUTION_ENABLED=false' in config
    assert 'P114_HUNYUAN_EXECUTION_ENABLED=false' in config
    assert 'default_blocked=True' in onboarding
    assert 'P114_WAN_LICENSE_ACKNOWLEDGED' in onboarding
    assert 'AcknowledgeWanApache2License' in setup
    assert 'Get-FileHash' in setup
    assert 'Wan22ImageToVideoLatent' in setup
    for forbidden in ("Invoke-WebRequest", "Start-BitsTransfer", "huggingface-cli download", "wget ", "curl "):
        assert forbidden not in setup


def test_worker_keeps_cost_review_and_publishing_boundaries() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "GenerationJobType.LOCAL_CLIP" in source
    assert 'providers=("local-comfyui",)' in source
    assert "configured workflow hash no longer matches" in source
    assert "model file hash mismatch" in source
    assert "evaluate_model_policy" in source
    assert 'actual_cost_usd=Decimal("0")' in source
    assert '"human_review_required": True' in source
    assert '"automatic_approval": False' in source
    assert '"automatic_publishing": False' in source
    assert "ffprobe" in source
    assert "LocalVideoCancelled" in source


def test_authenticated_api_and_optional_supervisor_are_wired() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    factory = FACTORY.read_text(encoding="utf-8")
    supervisor = SUPERVISOR.read_text(encoding="utf-8")
    for route in (
        "/local-video/profiles",
        "/local-video/preflight",
        "/local-video/jobs",
        "/local-video/jobs/{job_id}",
    ):
        assert route in runtime
    assert "OperatorIdentity = Depends(authenticate)" in runtime
    assert "install_local_video_routes" in factory
    assert "P114_LOCAL_VIDEO_ENABLED" in supervisor
    assert "p114_local_video_worker" in supervisor


def test_windows_upgrade_advances_complete_schema_without_replacing_keys() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    deploy = DEPLOY.read_text(encoding="utf-8")
    assert "OPS_MIGRATION_HEAD=0100_p114_pilot_attempt_binding.sql" in config
    assert '$values["OPS_MIGRATION_HEAD"] = "0100_p114_pilot_attempt_binding.sql"' in deploy
    assert "p114_renderer_onboarding" in deploy
    assert "OPERATOR_API_KEYS_JSON" not in deploy
