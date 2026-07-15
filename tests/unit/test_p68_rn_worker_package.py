from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "deploy" / "p68-rn-worker"


def test_rn_worker_is_pinned_private_and_requires_models() -> None:
    dockerfile = (WORKER / "Dockerfile").read_text(encoding="utf-8")
    compose = (WORKER / "compose.yaml").read_text(encoding="utf-8")
    entrypoint = (WORKER / "entrypoint.sh").read_text(encoding="utf-8")
    assert "ARG COMFYUI_REF" in dockerfile
    assert 'test -n "$COMFYUI_REF"' in dockerfile
    assert "127.0.0.1" in compose
    assert "capabilities: [gpu]" in compose
    for filename in (
        "wan2.2_ti2v_5B_fp16.safetensors",
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan2.2_vae.safetensors",
    ):
        assert filename in entrypoint


def test_wan_api_workflow_has_dynamic_portrait_generation_contract() -> None:
    workflow = json.loads((WORKER / "workflows" / "wan22-ti2v-5b-api.json").read_text(encoding="utf-8"))
    classes = {node["class_type"] for node in workflow.values()}
    assert {"LoadImage", "Wan22ImageToVideoLatent", "KSampler", "CreateVideo", "SaveVideo"} <= classes
    serialized = json.dumps(workflow)
    for token in (
        "{{INPUT_IMAGE}}",
        "{{POSITIVE_PROMPT}}",
        "{{NEGATIVE_PROMPT}}",
        "{{SEED}}",
        "{{WIDTH}}",
        "{{HEIGHT}}",
        "{{FRAME_COUNT}}",
        "{{FPS}}",
        "{{OUTPUT_PREFIX}}",
    ):
        assert token in serialized


def test_unverified_model_checksums_keep_publication_blocked() -> None:
    manifest = json.loads((WORKER / "model-manifest.json").read_text(encoding="utf-8"))
    assert manifest["license"]["approval_status"] == "pending_snapshot_verification"
    assert manifest["publish_allowed"] is False
    assert any(item["sha256"] is None for item in manifest["files"])
    assert any(item["source_revision"] is None for item in manifest["files"])


def test_model_downloader_requires_pinned_repository_revisions() -> None:
    downloader = (WORKER / "download-models.sh").read_text(encoding="utf-8")
    assert "WAN22_REVISION" in downloader
    assert "WAN21_REVISION" in downloader
    assert downloader.count('--revision "${wan22_revision}"') == 2
    assert '--revision "${wan21_revision}"' in downloader
