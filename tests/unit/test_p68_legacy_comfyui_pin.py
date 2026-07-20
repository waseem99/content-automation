from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = "v0.3.26"


def test_local_preview_uses_one_legacy_comfyui_pin() -> None:
    setup = (ROOT / "scripts/windows/setup_p68_local_keyframe_worker.ps1").read_text(encoding="utf-8")
    example = (ROOT / "deploy/p68-local-keyframe-worker/.env.example").read_text(encoding="utf-8")
    dockerfile = (ROOT / "deploy/p68-local-keyframe-worker/Dockerfile").read_text(encoding="utf-8")
    readme = (ROOT / "deploy/p68-local-keyframe-worker/README.md").read_text(encoding="utf-8")

    assert f'$comfyUiRef = "{PIN}"' in setup
    assert f"COMFYUI_REF={PIN}" in example
    assert "comfy-(aimdo|kitchen)" in dockerfile
    assert "comfy_aimdo" in dockerfile
    assert f"ComfyUI release: `{PIN}`" in readme
