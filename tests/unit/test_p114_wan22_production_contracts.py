from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from src.application.local_video import manifest as manifest_module
from src.application.local_video.manifest import (
    select_resolution,
    verify_comfyui_commit,
    verify_model_bundle,
)
from src.application.local_video.models import LocalVideoJobStatus, LocalVideoRequest
from src.application.local_video.provider import ComfyUILocalVideoProvider


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "config" / "local-video-workflows" / "wan22-ti2v-5b-api.json"
MANIFEST = ROOT / "config" / "local-video-workflows" / "wan22-ti2v-5b.manifest.json"
ACTIVATION = ROOT / "src" / "operations" / "p114_wan22_activation.py"
PIPELINE = ROOT / "src" / "operations" / "local_pipeline.py"
ALWAYS_ON_PIPELINE = ROOT / "src" / "operations" / "always_on_pipeline.py"
LOCAL_VIDEO_WORKER = ROOT / "src" / "operations" / "local_video_worker.py"
PREVIEW_WORKER = ROOT / "src" / "operations" / "local_worker_v2.py"
SUPERVISOR = ROOT / "scripts" / "windows" / "supervise_local_production.ps1"
ACTIVATE_PS = ROOT / "scripts" / "windows" / "activate_p114_wan22.ps1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(tmp_path: Path) -> LocalVideoRequest:
    image = tmp_path / "approved-keyframe.png"
    image.write_bytes(b"p114-approved-keyframe")
    return LocalVideoRequest(
        generation_job_id=UUID("00000000-0000-0000-0000-000000000101"),
        generation_attempt_id=UUID("00000000-0000-0000-0000-000000000102"),
        pilot_case_id=None,
        provider_key="wan-ai",
        model_key="Wan2.2-TI2V-5B",
        workflow_key="wan22-ti2v-5b-production",
        workflow_path=WORKFLOW,
        workflow_sha256=_sha(WORKFLOW),
        checkpoint_sha256="228930fb595f98d665fe07b1a823d8feebe4208ac329f1d05b5f6e604cc75168",
        input_image_path=image,
        end_image_path=None,
        prompt="Preserve the approved scene and add subtle natural motion.",
        negative_prompt="text, watermark, warped anatomy",
        seed=42,
        width=480,
        height=832,
        fps=24,
        frame_count=49,
        inference_steps=20,
        output_prefix="p114-video/proof/attempt-1",
    )


def test_manifest_pins_validated_workflow_and_model_bundle() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["workflow_sha256"] == _sha(WORKFLOW)
    assert manifest["model_bundle_sha256"] == "228930fb595f98d665fe07b1a823d8feebe4208ac329f1d05b5f6e604cc75168"
    assert manifest["tested_comfyui_commit"] == "a8c44f9b2a0678ac4082e3529a3f43db7472acfe"
    assert manifest["tested_workstation"]["gpu"] == "NVIDIA GeForce GTX 1080"
    assert manifest["activation"]["hunyuan_enabled"] is False
    assert manifest["activation"]["automatic_publishing"] is False
    assert manifest["default_steps"] == 12
    assert {item["path"] for item in manifest["model_files"]} == {
        "diffusion_models/wan2.2_ti2v_5B_fp16.safetensors",
        "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "vae/wan2.2_vae.safetensors",
    }


def test_workflow_is_api_format_and_runtime_parameterized() -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    assert workflow["56"]["class_type"] == "LoadImage"
    assert workflow["56"]["inputs"]["image"] == "{{INPUT_IMAGE}}"
    assert workflow["3"]["inputs"]["steps"] == "{{INFERENCE_STEPS}}"
    assert workflow["55"]["inputs"]["width"] == "{{WIDTH}}"
    assert workflow["55"]["inputs"]["height"] == "{{HEIGHT}}"
    assert workflow["55"]["inputs"]["length"] == "{{FRAME_COUNT}}"
    assert workflow["58"]["inputs"]["filename_prefix"] == "{{OUTPUT_PREFIX}}"
    assert all(isinstance(node.get("inputs"), dict) and node.get("class_type") for node in workflow.values())


def test_provider_uploads_p87_keyframe_before_submitting_workflow(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/upload/image":
            return httpx.Response(200, json={"name": "p114-uploaded-keyframe.png", "type": "input"})
        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            prompt = payload["prompt"]
            assert prompt["56"]["inputs"]["image"] == "p114-uploaded-keyframe.png"
            assert prompt["3"]["inputs"]["steps"] == 20
            assert prompt["55"]["inputs"]["width"] == 480
            assert prompt["55"]["inputs"]["height"] == 832
            assert prompt["58"]["inputs"]["filename_prefix"] == "p114-video/proof/attempt-1"
            return httpx.Response(200, json={"prompt_id": "wan-proof-1"})
        raise AssertionError(request.url.path)

    client = httpx.Client(
        base_url="http://127.0.0.1:8188",
        transport=httpx.MockTransport(handler),
        trust_env=False,
    )
    provider = ComfyUILocalVideoProvider(base_url="http://127.0.0.1:8188", client=client)
    job = provider.submit(_request(tmp_path))
    assert job.status == LocalVideoJobStatus.QUEUED
    assert job.provider_job_id == "wan-proof-1"
    assert [request.url.path for request in seen] == ["/upload/image", "/prompt"]
    client.close()


def test_provider_extracts_comfyui_execution_timing() -> None:
    metrics = ComfyUILocalVideoProvider._execution_metrics(
        {
            "messages": [
                ["execution_start", {"timestamp": 1000}],
                ["execution_success", {"timestamp": 4250}],
            ]
        }
    )
    assert metrics["gpu_active_ms"] == 3250
    assert metrics["measurement"] == "comfyui_execution_messages"


def test_worker_verifies_exact_model_files_and_bundle(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    files = []
    for relative, content in (
        ("diffusion_models/model.safetensors", b"model"),
        ("text_encoders/clip.safetensors", b"clip"),
        ("vae/vae.safetensors", b"vae"),
    ):
        path = model_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        files.append({"path": relative, "sha256": _sha(path)})
    bundle = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    verified = verify_model_bundle(
        {"capabilities": {"model_files": files}, "checkpoint_sha256": bundle},
        model_root=model_root,
    )
    assert verified["bundle_sha256"] == bundle
    (model_root / "vae/vae.safetensors").write_bytes(b"drift")
    with pytest.raises(RuntimeError, match="model hash mismatch"):
        verify_model_bundle(
            {"capabilities": {"model_files": files}, "checkpoint_sha256": bundle},
            model_root=model_root,
        )


def test_model_verification_cache_reuses_hashes_until_file_signature_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_root = tmp_path / "models"
    files = []
    for relative, content in (
        ("diffusion_models/model.safetensors", b"model"),
        ("text_encoders/clip.safetensors", b"clip"),
        ("vae/vae.safetensors", b"vae"),
    ):
        path = model_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        files.append({"path": relative, "sha256": _sha(path)})
    bundle = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    calls = 0
    original = manifest_module.sha256_file

    def counted(path: Path) -> str:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(manifest_module, "sha256_file", counted)
    first = verify_model_bundle(
        {"capabilities": {"model_files": files}, "checkpoint_sha256": bundle},
        model_root=model_root,
    )
    second = verify_model_bundle(
        {"capabilities": {"model_files": files}, "checkpoint_sha256": bundle},
        model_root=model_root,
    )
    assert first["verification_cache_hit"] is False
    assert second["verification_cache_hit"] is True
    assert calls == 3


def test_comfyui_commit_is_verified_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "ComfyUI"
    (root / ".git").mkdir(parents=True)
    (root / "main.py").write_text("# comfy", encoding="utf-8")
    expected = "a" * 40

    class Result:
        returncode = 0
        stdout = expected + "\n"
        stderr = ""

    monkeypatch.setattr(manifest_module.subprocess, "run", lambda *args, **kwargs: Result())
    verified = verify_comfyui_commit(root, expected)
    assert verified["actual_commit"] == expected

    with pytest.raises(RuntimeError, match="commit mismatch"):
        verify_comfyui_commit(root, "b" * 40)


def test_provider_rejects_embedded_unresolved_tokens(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "prefix-{{UNKNOWN_TOKEN}}"},
                }
            }
        ),
        encoding="utf-8",
    )
    request = _request(tmp_path)
    request = LocalVideoRequest(
        **{
            **request.__dict__,
            "workflow_path": workflow,
            "workflow_sha256": _sha(workflow),
        }
    )
    provider = ComfyUILocalVideoProvider(base_url="http://127.0.0.1:8188")
    try:
        with pytest.raises(RuntimeError, match="unresolved tokens"):
            provider.workflow_for(request, uploaded_input_name="input.png")
    finally:
        provider.client.close()


def test_portrait_and_landscape_resolution_selection() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    supported = manifest["supported_resolutions"]
    assert select_resolution(704, 1280, supported) == (480, 832)
    assert select_resolution(1280, 704, supported) == (832, 480)


def test_repository_wires_approved_keyframes_to_animated_previews() -> None:
    activation = ACTIVATION.read_text(encoding="utf-8")
    pipeline = PIPELINE.read_text(encoding="utf-8")
    always_on_pipeline = ALWAYS_ON_PIPELINE.read_text(encoding="utf-8")
    local_video_worker = LOCAL_VIDEO_WORKER.read_text(encoding="utf-8")
    preview = PREVIEW_WORKER.read_text(encoding="utf-8")
    supervisor = SUPERVISOR.read_text(encoding="utf-8")

    assert "manual_keyframe_required\": False" in activation
    assert "auto_selected_approved_keyframe" in activation
    assert "input_keyframe_asset_id" in pipeline
    assert "local_clips_pending" in pipeline
    assert "local_clip_job_id" in pipeline
    assert 'render_mode = "animated_local_clips"' in pipeline
    assert 'row_render_mode = "static_keyframes_fallback"' in pipeline
    assert 'row_render_mode = "static_keyframes_fallback"' in always_on_pipeline
    assert "scene_lineage_sha256" in pipeline
    assert "P114_RETRY_DELAY_SECONDS" in local_video_worker
    assert "verify_comfyui_commit" in local_video_worker
    assert 'expected_kind="local_comfyui_video"' in preview
    assert '"animated_scene_count": len(local_clip_job_ids)' in preview
    assert '"render_mode": str(payload.get("render_mode")' in preview
    assert 'New-ManagedState "comfyui"' in supervisor
    assert 'New-ManagedState "local-video-worker"' in supervisor
    assert "Test-ComfyUIReady" in supervisor
    assert "P114_LOCAL_VIDEO_ENABLED" in supervisor


def test_windows_activation_is_one_command_fail_closed_and_always_on() -> None:
    script = ACTIVATE_PS.read_text(encoding="utf-8")
    env = (ROOT / "config" / "local.env.example").read_text(encoding="utf-8")
    assert 'P114_LOCAL_VIDEO_ENABLED"] = if ($Enabled)' in script
    assert 'src.operations.p114_wan22_activation", "onboard"' in script
    assert 'src.operations.p114_wan22_activation", "proof"' in script
    assert "Start-TemporaryComfyUI" in script
    assert "Stop-TemporaryComfyUI" in script
    assert "Set-P114Enabled $values $false" in script
    assert "Set-P114Enabled $values $true" in script
    assert "Start-ScheduledTask" in script
    assert "automatic_publishing = $false" in script
    assert 'P114_RETRY_DELAY_SECONDS"] = "20"' in script
    assert "P114_COMFYUI_ROOT=D:\\ComfyUI\\App" in env
    assert "P114_COMFYUI_PYTHON=D:\\ComfyUI\\App\\.venv\\Scripts\\python.exe" in env
