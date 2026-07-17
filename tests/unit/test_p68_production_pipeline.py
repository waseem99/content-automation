from __future__ import annotations

import json
from pathlib import Path

from src.p68_production_pipeline import prepare_asset_manifest


def test_asset_manifest_marks_master_reuse_as_preview_only(tmp_path: Path) -> None:
    pilot, artifacts = tmp_path / "pilot", tmp_path / "artifacts"
    pilot.mkdir()
    (pilot / "content-plan.json").write_text(
        json.dumps({"pilot_id": "pilot", "shots": [{"shot_id": "S01"}, {"shot_id": "S02"}]}),
        encoding="utf-8",
    )
    generated = artifacts / "generated-assets"
    generated.mkdir(parents=True)
    (generated / "master-test.png").write_bytes(b"master")

    result = prepare_asset_manifest(pilot, artifacts)

    assert result["all_shots_have_derived_assets"] is False
    assert all(item["quality_status"] == "preview_only" for item in result["assets"])
    assert result["publish_allowed"] is False


def test_asset_manifest_prefers_shot_specific_asset(tmp_path: Path) -> None:
    pilot, artifacts = tmp_path / "pilot", tmp_path / "artifacts"
    pilot.mkdir()
    (pilot / "content-plan.json").write_text(
        json.dumps({"pilot_id": "pilot", "shots": [{"shot_id": "S01"}]}), encoding="utf-8"
    )
    generated = artifacts / "generated-assets"
    generated.mkdir(parents=True)
    (generated / "master-test.png").write_bytes(b"master")
    shot = generated / "s01-final.png"
    shot.write_bytes(b"shot")

    result = prepare_asset_manifest(pilot, artifacts)

    assert result["all_shots_have_derived_assets"] is True
    assert result["assets"][0]["path"] == str(shot)
    assert result["assets"][0]["quality_status"] == "pending_final_review"


def test_asset_manifest_can_honestly_designate_master_as_generation_keyframe(tmp_path: Path) -> None:
    pilot, artifacts = tmp_path / "pilot", tmp_path / "artifacts"
    pilot.mkdir()
    (pilot / "content-plan.json").write_text(
        json.dumps({"pilot_id": "pilot", "shots": [{"shot_id": "S01"}]}), encoding="utf-8"
    )
    generated = artifacts / "generated-assets"
    generated.mkdir(parents=True)
    master = generated / "master-test.png"
    master.write_bytes(b"master")
    (generated / "shot-keyframes.json").write_text(
        json.dumps(
            {
                "shots": {
                    "S01": {
                        "path": master.name,
                        "approved_for_generation": True,
                        "reason": "The continuity master was authored as the opening frame.",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = prepare_asset_manifest(pilot, artifacts)

    assert result["assets"][0]["source"] == "designated_continuity_master_keyframe"
    assert result["assets"][0]["quality_status"] == "pending_final_review"
    assert result["all_shots_have_derived_assets"] is False
    assert result["all_shots_have_generation_keyframes"] is True
