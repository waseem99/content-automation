from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from src.p68_keyframe_batch import approve_keyframe, build_keyframe_work_orders, intake_keyframe
from src.p68_production_pipeline import prepare_asset_manifest


ROOT = Path(__file__).resolve().parents[2]


def image(path: Path, size: tuple[int, int] = (900, 1600)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (24, 48, 72)).save(path)
    return path


def test_repository_work_orders_cover_only_natural_motion_shots(tmp_path: Path) -> None:
    result = build_keyframe_work_orders(ROOT / "p68-pilots", tmp_path)

    assert result["pilot_count"] == 6
    assert result["roster_complete"] is True
    assert result["natural_motion_keyframes_required"] == 29
    assert result["approved_keyframes"] == 0
    assert result["keyframes_awaiting_asset_or_review"] == 29
    assert result["all_keyframes_ready"] is False
    assert result["generation_calls_made"] == 0
    assert result["vercel_deployment_required"] is False
    assert all("still_image_prompt" in order for pilot in result["pilots"] for order in pilot["orders"])


def test_intake_validates_provenance_and_requires_separate_approval(tmp_path: Path) -> None:
    source = image(tmp_path / "source.png")
    result = intake_keyframe(
        pilots_root=ROOT / "p68-pilots", artifact_root=tmp_path / "artifacts",
        pilot_id="animal-octopus-arms", shot_id="S01", source_path=source,
        source_kind="generated_original", provider="local-image-model",
        model_or_collection="fixture-v1", rights_evidence="generated for this project",
    )
    assert result["image_probe"]["passed"] is True
    assert result["human_review_status"] == "pending_keyframe_review"
    assert result["approved_for_generation"] is False
    assert result["publish_allowed"] is False

    approved = approve_keyframe(
        artifact_root=tmp_path / "artifacts", pilot_id="animal-octopus-arms", shot_id="S01",
        reviewer="creative-director", note="Identity, anatomy, light, and composition match the continuity bible.",
    )
    assert approved["human_review_status"] == "approved_for_generation"
    designations = json.loads(Path(approved["designation_path"]).read_text())
    assert designations["shots"]["S01"]["approved_for_generation"] is True
    assert designations["shots"]["S01"]["publish_allowed"] is False


def test_unapproved_intake_is_visible_but_blocked_in_asset_manifest(tmp_path: Path) -> None:
    pilot = tmp_path / "pilots" / "animal-octopus-arms"
    pilot.mkdir(parents=True)
    source_plan = json.loads((ROOT / "p68-pilots/animal-octopus-arms/content-plan.json").read_text())
    source_plan["shots"] = source_plan["shots"][:1]
    (pilot / "content-plan.json").write_text(json.dumps(source_plan))
    source = image(tmp_path / "source.png")
    artifacts = tmp_path / "artifacts" / "gold" / "animal-octopus-arms"
    image(artifacts / "generated-assets" / "master-test.png")
    intake_keyframe(
        pilots_root=tmp_path / "pilots", artifact_root=tmp_path / "artifacts",
        pilot_id="animal-octopus-arms", shot_id="S01", source_path=source,
        source_kind="generated_original", provider="local", model_or_collection="fixture",
        rights_evidence="generated for fixture",
    )

    manifest = prepare_asset_manifest(pilot, artifacts)
    assert manifest["assets"][0]["quality_status"] == "pending_keyframe_review"
    assert manifest["publish_allowed"] is False


def test_rejects_landscape_or_small_keyframe(tmp_path: Path) -> None:
    source = image(tmp_path / "bad.png", (640, 360))
    with pytest.raises(ValueError, match="failed validation"):
        intake_keyframe(
            pilots_root=ROOT / "p68-pilots", artifact_root=tmp_path / "artifacts",
            pilot_id="rawr-gecko-grip", shot_id="S01", source_path=source,
            source_kind="generated_original", provider="local", model_or_collection="fixture",
            rights_evidence="generated for fixture",
        )
