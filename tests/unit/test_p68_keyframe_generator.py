from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from PIL import Image

from src.p68_keyframe_generator import KeyframeGenerationController, build_keyframe_requests
from src.p68_keyframe_provider import ImageJob, ImageJobStatus


ROOT = Path(__file__).resolve().parents[2]


class FakeProvider:
    name = "local-comfyui-keyframe"
    requires_paid_approval = False

    def __init__(self) -> None:
        self.jobs: list[ImageJob] = []

    def submit(self, request):
        job = ImageJob(self.name, f"job-{len(self.jobs)+1}", request.idempotency_key, ImageJobStatus.QUEUED, "now", request.model_id)
        self.jobs.append(job)
        return job

    def poll(self, job):
        return replace(job, status=ImageJobStatus.SUCCEEDED, output_descriptor={"filename": "x.png"})

    def download(self, job, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (900, 1600), (20, 40, 60)).save(output_path)
        return output_path


def controller(tmp_path: Path, provider: FakeProvider) -> KeyframeGenerationController:
    return KeyframeGenerationController(
        pilots_root=ROOT / "p68-pilots", artifact_root=tmp_path, provider=provider,
        checkpoint="fixture.safetensors", license_type="test-license", license_url="https://license.test",
        gpu_hourly_usd=Decimal("1.2"), soft_cap_usd=Decimal("1"), hard_cap_usd=Decimal("2"),
    )


def test_repository_builds_29_deterministic_requests(tmp_path: Path) -> None:
    requests = build_keyframe_requests(ROOT / "p68-pilots", tmp_path)
    assert len(requests) == 29
    assert len({item.idempotency_key for item in requests}) == 29


def test_bounded_submit_refreshes_into_unapproved_provenance(tmp_path: Path) -> None:
    provider = FakeProvider()
    ctl = controller(tmp_path, provider)
    requests = build_keyframe_requests(ROOT / "p68-pilots", tmp_path, pilot_id="animal-octopus-arms")
    submitted = ctl.submit_missing(requests, limit=2, expected_runtime_seconds=Decimal("120"))
    assert len(submitted["submitted"]) == 2
    assert all(item["reason"] == "bounded_batch_limit" for item in submitted["blocked"])
    refreshed = ctl.refresh()
    assert len(refreshed["completed"]) == 2
    assert all(item["human_review_status"] == "pending_keyframe_review" for item in refreshed["completed"])
    assert ctl.status()["counts"]["succeeded"] == 2
    assert ctl.status()["publish_allowed"] is False
