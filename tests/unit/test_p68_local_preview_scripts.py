from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_setup_and_sample_scripts_preserve_review_only_boundaries() -> None:
    setup = (ROOT / "scripts/windows/setup_p68_local_keyframe_worker.ps1").read_text(encoding="utf-8")
    sample = (ROOT / "scripts/windows/run_p68_local_keyframe_sample.ps1").read_text(encoding="utf-8")
    download = (ROOT / "scripts/windows/download_p68_sdxl_preview_model.ps1").read_text(encoding="utf-8")

    assert "-AcceptModelLicense" in download
    assert "publish_allowed = $false" in download
    assert "P68_KEYFRAME_EXECUTION_MODE=local_preview" in setup
    assert "P68_KEYFRAME_WIDTH=704" in setup
    assert "P68_KEYFRAME_HEIGHT=1280" in setup
    assert "--limit 1" in sample
    assert "pending_keyframe_review" in sample
    assert "Approved for video generation: false" in sample
    assert "Publish allowed: false" in sample


def test_sdxl_download_url_uses_braced_powershell_variables() -> None:
    download = (ROOT / "scripts/windows/download_p68_sdxl_preview_model.ps1").read_text(encoding="utf-8")

    assert "/resolve/${modelRevision}/${modelName}?download=true" in download
    assert "$modelName?download" not in download


def test_local_worker_is_loopback_only_and_does_not_include_wan_models() -> None:
    compose = (ROOT / "deploy/p68-local-keyframe-worker/compose.yaml").read_text(encoding="utf-8")
    entrypoint = (ROOT / "deploy/p68-local-keyframe-worker/entrypoint.sh").read_text(encoding="utf-8")

    assert "127.0.0.1" in compose
    assert "P68_KEYFRAME_CHECKPOINT" in entrypoint
    assert "wan2.2" not in compose.lower()
    assert "wan2.2" not in entrypoint.lower()


def test_local_worker_pins_and_verifies_pascal_compatible_torch() -> None:
    dockerfile = (ROOT / "deploy/p68-local-keyframe-worker/Dockerfile").read_text(encoding="utf-8")
    entrypoint = (ROOT / "deploy/p68-local-keyframe-worker/entrypoint.sh").read_text(encoding="utf-8")

    assert "torch==${P68_TORCH_VERSION}" in dockerfile
    assert "P68_TORCH_VERSION=2.7.0" in dockerfile
    assert "P68_TORCHVISION_VERSION=0.22.0" in dockerfile
    assert "P68_TORCHAUDIO_VERSION=2.7.0" in dockerfile
    assert 'assert "sm_61" in compiled_arches' in dockerfile
    assert "torch.cuda.is_available()" in entrypoint
    assert "torch.cuda.get_device_capability(0)" in entrypoint
    assert "required_arch not in compiled_arches" in entrypoint
