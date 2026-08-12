from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.operations.animal_x_month_preproduction import (
    BRAND_SLUG,
    CORE_OUTPUT_TARGET,
    FINAL_MASTERS_PER_PILLAR,
    MASTER_DURATION_SECONDS,
    MASTER_TARGET,
    MASTER_TARGET_PLATFORMS,
    PILLARS,
    PROHIBITED_VIDEO_JOB_TYPES,
    SHORTS_PER_MASTER,
    SHORT_DURATION_SECONDS,
    SHORT_TARGET_PLATFORMS,
    AnimalXPreproductionError,
    publication_slots,
    scene_windows,
)


def test_animal_x_month_shape_is_twenty_families_sixty_core_outputs() -> None:
    assert BRAND_SLUG == "animal-x"
    assert MASTER_TARGET == 20
    assert SHORTS_PER_MASTER == 2
    assert CORE_OUTPUT_TARGET == 60
    assert MASTER_DURATION_SECONDS == 135
    assert SHORT_DURATION_SECONDS == 60
    assert len(PILLARS) == 4
    assert FINAL_MASTERS_PER_PILLAR == 5
    assert set(MASTER_TARGET_PLATFORMS) == {"youtube", "facebook", "instagram"}
    assert set(SHORT_TARGET_PLATFORMS) == {
        "facebook",
        "instagram",
        "tiktok",
        "youtube_shorts",
    }


def test_september_calendar_has_exactly_two_core_outputs_per_day() -> None:
    families = [f"family-{index:02d}" for index in range(1, 21)]
    rows = publication_slots(date(2026, 9, 1), families)
    assert len(rows) == 60
    by_day: dict[str, list[dict]] = {}
    for row in rows:
        by_day.setdefault(row["date"], []).append(row)
    assert len(by_day) == 30
    assert all(len(items) == 2 for items in by_day.values())
    assert sum(row["output"] == "master" for row in rows) == 20
    assert sum(row["output"] == "short_1" for row in rows) == 20
    assert sum(row["output"] == "short_2" for row in rows) == 20


def test_two_per_day_exact_profile_rejects_non_thirty_day_month() -> None:
    with pytest.raises(AnimalXPreproductionError, match="30-day"):
        publication_slots(date(2026, 10, 1), [f"family-{index}" for index in range(20)])


def test_short_windows_are_noninventive_master_scene_extracts() -> None:
    scenes = [
        {
            "id": f"scene-{index}",
            "sequence": index,
            "scene_key": f"S{index:02d}",
            "narration_text": f"Master narration {index}",
            "target_duration_seconds": 20,
        }
        for index in range(1, 7)
    ]
    plans = scene_windows(scenes)
    assert len(plans) == 2
    assert {plan["short_index"] for plan in plans} == {1, 2}
    assert all(plan["new_factual_claims_allowed"] is False for plan in plans)
    assert all(plan["source_strategy"] == "approved_master_scene_extract" for plan in plans)
    left = set(plans[0]["scene_ids"])
    right = set(plans[1]["scene_ids"])
    assert left
    assert right
    assert left.isdisjoint(right)
    assert all(plan["planned_duration_seconds"] <= SHORT_DURATION_SECONDS for plan in plans)


def test_runner_has_hard_no_video_generation_boundary() -> None:
    source = Path("src/operations/animal_x_month_preproduction.py").read_text(encoding="utf-8")
    assert set(PROHIBITED_VIDEO_JOB_TYPES) == {
        "local_clip",
        "premium_clip",
        "preview",
        "assembly",
        "publishing",
    }
    prohibited_execution_tokens = (
        "ProviderExecutionService(",
        "HybridRoutingService(",
        "DeliveryService(",
        "PROVIDER_PAID_EXECUTION_ENABLED=true",
        "HYBRID_PAID_EXECUTION_ENABLED=true",
        "HYBRID_PUBLIC_PUBLISHING_ENABLED=true",
        "P114_LOCAL_VIDEO_ENABLED=true",
    )
    for token in prohibited_execution_tokens:
        assert token not in source
    assert '"provider_spend_enabled_by_this_run": False' in source
    assert '"public_publishing_enabled_by_this_run": False' in source
    assert '"final_video_generation_deferred": True' in source


def test_audio_is_generated_but_not_auto_approved() -> None:
    source = Path("src/operations/animal_x_month_preproduction.py").read_text(encoding="utf-8")
    assert "AudioProductionService" in source
    assert '"automatic_audio_approval": False' in source
    assert '"human_audio_review_required_before_final_video": True' in source
    assert ".decide(" not in source
