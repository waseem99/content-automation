from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from src.p68_clip_generator import ClipGenerationController, build_requests
from src.p68_generation_governance import GenerationBudget, TermsEvidence
from src.p68_video_provider import VideoJob, VideoJobStatus


def write_fixture(tmp_path: Path, source: str) -> tuple[Path, Path]:
    pilot, artifacts = tmp_path / "pilot", tmp_path / "artifacts"
    pilot.mkdir()
    (pilot / "content-plan.json").write_text(
        json.dumps(
            {
                "pilot_id": "pilot",
                "shots": [
                    {
                        "shot_id": "S01",
                        "story_stage": "hook",
                        "duration_seconds": 5,
                        "transition_handle_seconds": 0.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (pilot / "clip-prompts.json").write_text(
        json.dumps(
            [
                {
                    "shot_id": "S01",
                    "prompt": "Natural documentary movement",
                    "negative_prompt": "distortion",
                    "entry_action": "foot settles",
                    "exit_action": "subject pauses",
                }
            ]
        ),
        encoding="utf-8",
    )
    image = artifacts / "generated-assets" / "s01.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"image")
    manifest = artifacts / "assets" / "asset-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "shot_id": "S01",
                        "path": str(image),
                        "source": source,
                        "rights_status": "generated_for_project",
                        "quality_status": "pending_final_review",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return pilot, artifacts


def test_real_generation_requires_shot_specific_keyframe(tmp_path: Path) -> None:
    pilot, artifacts = write_fixture(tmp_path, "continuity_master_preview_fallback")
    with pytest.raises(ValueError, match="shot-specific keyframe"):
        build_requests(pilot, artifacts)


def test_builds_two_deterministic_natural_motion_variants(tmp_path: Path) -> None:
    pilot, artifacts = write_fixture(tmp_path, "derived_shot_asset")
    requests = build_requests(pilot, artifacts, variants=2)
    assert len(requests) == 2
    assert requests[0].seed != requests[1].seed
    assert requests[0].duration_seconds == 5.5
    assert "Motion must begin immediately" in requests[0].prompt
    assert "frozen subject" in requests[0].negative_prompt
    assert requests[0].metadata["engagement_priority"] == "hero"
    assert requests[0].idempotency_key == build_requests(pilot, artifacts, variants=2)[0].idempotency_key


def test_shot_filter_can_submit_ready_shots_without_unready_neighbors(tmp_path: Path) -> None:
    pilot, artifacts = write_fixture(tmp_path, "derived_shot_asset")
    requests = build_requests(pilot, artifacts, variants=1, shot_ids={"S02"})
    assert requests == []


def test_hero_variant_budget_can_exceed_standard_variant_count(tmp_path: Path) -> None:
    pilot, artifacts = write_fixture(tmp_path, "derived_shot_asset")
    requests = build_requests(pilot, artifacts, variants=1, hero_variants=2)
    assert len(requests) == 2


class FakeProvider:
    name = "fake-rn"
    requires_paid_approval = False

    def __init__(self, *, fail_download: bool = False) -> None:
        self.fail_download = fail_download
        self.submitted: list[VideoJob] = []

    def health(self) -> dict[str, object]:
        return {"healthy": True}

    def submit(self, request: object) -> VideoJob:
        job = VideoJob(
            self.name,
            f"job-{len(self.submitted) + 1}",
            request.idempotency_key,
            VideoJobStatus.QUEUED,
            "now",
            request.model_id,
        )
        self.submitted.append(job)
        return job

    def poll(self, job: VideoJob) -> VideoJob:
        return replace(
            job,
            status=VideoJobStatus.SUCCEEDED,
            output_descriptor={"filename": "clip.mp4", "type": "output"},
        )

    def download(self, job: VideoJob, output_path: Path) -> Path:
        if self.fail_download:
            raise RuntimeError("download failed")
        target = output_path.with_suffix(".mp4")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"video")
        return target

    def cancel(self, job: VideoJob) -> VideoJob:
        return replace(job, status=VideoJobStatus.CANCELLED)


def terms() -> TermsEvidence:
    return TermsEvidence(
        provider="fake-rn",
        model_id="wan2.2-ti2v-5b",
        license_type="Apache-2.0",
        license_url="https://example.test/license",
        terms_snapshot_sha256="a" * 64,
        commercial_use_allowed=True,
        modification_allowed=True,
        captured_at="now",
    )


def test_pending_jobs_reserve_budget_before_more_submissions(tmp_path: Path) -> None:
    pilot, artifacts = write_fixture(tmp_path, "derived_shot_asset")
    first = build_requests(pilot, artifacts, variants=1)[0]
    second = replace(first, seed=first.seed + 1)
    provider = FakeProvider()
    controller = ClipGenerationController(
        pilot_dir=pilot,
        artifact_dir=artifacts,
        provider=provider,
        budget=GenerationBudget(
            soft_cap_usd=Decimal("6"),
            hard_cap_usd=Decimal("20"),
            rn_gpu_hourly_usd=Decimal("10"),
        ),
        terms=terms(),
    )

    result = controller.submit_missing([first, second], expected_runtime_seconds=Decimal("1800"))

    assert len(result["submitted"]) == 1
    assert result["blocked"] == [{"shot_id": "S01", "decision": "needs_approval"}]
    assert controller.ledger.committed_spend_usd == Decimal("5.0000")


def test_failed_download_does_not_poison_job_as_succeeded(tmp_path: Path) -> None:
    pilot, artifacts = write_fixture(tmp_path, "derived_shot_asset")
    request = build_requests(pilot, artifacts, variants=1)[0]
    controller = ClipGenerationController(
        pilot_dir=pilot,
        artifact_dir=artifacts,
        provider=FakeProvider(fail_download=True),
        budget=GenerationBudget(),
        terms=terms(),
    )
    controller.submit_missing([request])

    with pytest.raises(RuntimeError, match="download failed"):
        controller.refresh()

    assert controller.ledger.payload["jobs"][0]["status"] == "queued"


def test_premium_provider_fails_closed_without_explicit_spend_approval(tmp_path: Path) -> None:
    pilot, artifacts = write_fixture(tmp_path, "derived_shot_asset")
    request = build_requests(pilot, artifacts, variants=1)[0]
    provider = FakeProvider()
    provider.requires_paid_approval = True
    controller = ClipGenerationController(
        pilot_dir=pilot,
        artifact_dir=artifacts,
        provider=provider,
        budget=GenerationBudget(),
        terms=terms(),
    )

    result = controller.submit_missing([request])

    assert result["submitted"] == []
    assert result["blocked"] == [{"shot_id": "S01", "decision": "needs_approval"}]
