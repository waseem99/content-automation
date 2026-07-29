import json
from pathlib import Path

from src.p79_month_factory import PRIORITY_BRANDS, REQUIRED_PILOT_FILES, build_month_factory


ROOT = Path(__file__).resolve().parents[2]


def _config() -> dict:
    return json.loads((ROOT / "config/portfolio-brands.staging.json").read_text(encoding="utf-8"))


def _build():
    return build_month_factory(_config(), pilots_root=ROOT / "p68-pilots", artifacts_root=ROOT / "p68-artifacts")


def _write_gecko_pilot(pilots_root: Path) -> None:
    directory = pilots_root / "rawr-gecko-grip"
    directory.mkdir(parents=True)
    for name in REQUIRED_PILOT_FILES:
        if name == "source-brief.json":
            content = json.dumps({"brand_profile": "rawr_nation", "topic": "How a gecko defeats gravity"})
        elif name.endswith(".json"):
            content = "{}"
        else:
            content = ""
        (directory / name).write_text(content, encoding="utf-8")


def test_four_priority_brands_have_honest_inventory_state() -> None:
    result = _build()
    brands = {brand["id"]: brand for brand in result["brands"]}

    assert tuple(brands) == PRIORITY_BRANDS
    assert result["summary"]["concepts_ready"] == 48
    assert result["summary"]["brands_with_complete_inventory"] == 2
    assert result["summary"]["brands_blocked_for_brief"] == 2
    assert brands["historiq"]["blocker"] == "account_brief_and_reference_review_required"
    assert brands["ani-films"]["conceptCount"] == 0


def test_work_is_split_into_six_item_batches_without_paid_or_publish_jobs() -> None:
    result = _build()
    rawr = [item for item in result["items"] if item["brand"] == "rawr-nation"]

    assert len(rawr) == 24
    assert {item["batch"] for item in rawr} == {1, 2, 3, 4}
    assert all(1 <= sum(item["batch"] == batch for item in rawr) <= 6 for batch in {1, 2, 3, 4})
    assert result["summary"]["paid_render_jobs_started"] == 0
    assert result["summary"]["publish_jobs_started"] == 0
    assert result["guardrails"]["vercel_deployment_performed"] is False


def test_pilot_pack_without_local_artifact_remains_at_script_review(tmp_path: Path) -> None:
    pilots_root = tmp_path / "p68-pilots"
    artifacts_root = tmp_path / "p68-artifacts"
    _write_gecko_pilot(pilots_root)

    result = build_month_factory(_config(), pilots_root=pilots_root, artifacts_root=artifacts_root)
    gecko = next(item for item in result["items"] if item["title"] == "How a gecko defeats gravity")

    assert gecko["pilotId"] == "rawr-gecko-grip"
    assert gecko["stage"] == "script"
    assert gecko["nextAction"] == "human_review_script_and_scene_plan"
    assert "script pack" in gecko["assets"]
    assert "preview" not in gecko["assets"]


def test_local_preview_is_discovered_only_when_artifacts_exist(tmp_path: Path) -> None:
    pilots_root = tmp_path / "p68-pilots"
    artifacts_root = tmp_path / "p68-artifacts"
    _write_gecko_pilot(pilots_root)
    artifact = artifacts_root / "gold" / "rawr-gecko-grip"
    narration = artifact / "narration" / "narration.wav"
    preview = artifact / "renders" / "visual-v1" / "final_review.mp4"
    narration.parent.mkdir(parents=True)
    preview.parent.mkdir(parents=True)
    narration.write_bytes(b"local-audio")
    preview.write_bytes(b"local-preview")

    result = build_month_factory(_config(), pilots_root=pilots_root, artifacts_root=artifacts_root)
    gecko = next(item for item in result["items"] if item["title"] == "How a gecko defeats gravity")

    assert gecko["pilotId"] == "rawr-gecko-grip"
    assert gecko["stage"] == "preview"
    assert gecko["nextAction"] == "human_review_before_paid_render"
    assert gecko["previewPath"].endswith("final_review.mp4")
    assert {"VO", "preview"}.issubset(gecko["assets"])


def test_invalid_batch_size_is_rejected() -> None:
    try:
        build_month_factory(_config(), pilots_root=ROOT / "p68-pilots", artifacts_root=ROOT / "p68-artifacts", batch_size=0)
    except ValueError as error:
        assert "batch_size" in str(error)
    else:
        raise AssertionError("invalid batch size was accepted")
