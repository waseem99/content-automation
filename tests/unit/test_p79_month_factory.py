import json
from pathlib import Path

from src.p79_month_factory import PRIORITY_BRANDS, build_month_factory


ROOT = Path(__file__).resolve().parents[2]


def _build():
    config = json.loads((ROOT / "config/portfolio-brands.staging.json").read_text(encoding="utf-8"))
    return build_month_factory(config, pilots_root=ROOT / "p68-pilots", artifacts_root=ROOT / "p68-artifacts")


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


def test_existing_gecko_pilot_is_discovered_as_a_reviewable_preview() -> None:
    result = _build()
    gecko = next(item for item in result["items"] if item["title"] == "How a gecko defeats gravity")

    assert gecko["pilotId"] == "rawr-gecko-grip"
    assert gecko["stage"] == "preview"
    assert gecko["nextAction"] == "human_review_before_paid_render"
    assert "preview" in gecko["assets"]


def test_invalid_batch_size_is_rejected() -> None:
    config = json.loads((ROOT / "config/portfolio-brands.staging.json").read_text(encoding="utf-8"))
    try:
        build_month_factory(config, pilots_root=ROOT / "p68-pilots", artifacts_root=ROOT / "p68-artifacts", batch_size=0)
    except ValueError as error:
        assert "batch_size" in str(error)
    else:
        raise AssertionError("invalid batch size was accepted")
