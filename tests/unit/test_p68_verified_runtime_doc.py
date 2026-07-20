from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_verified_runtime_record_matches_worker_base() -> None:
    doc = (ROOT / "docs/p68-verified-gtx1080-runtime.md").read_text(encoding="utf-8")
    dockerfile = (ROOT / "deploy/p68-local-keyframe-worker/Dockerfile").read_text(encoding="utf-8")
    image = "pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime"
    assert image in doc
    assert f"FROM {image}" in dockerfile
    assert "sm_61" in doc
    assert "pending human review" in doc
