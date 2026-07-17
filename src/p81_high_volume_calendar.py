"""Expand the reviewed Rawr Nation month into a four-originals-per-day calendar."""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Any

from src.p80_brand_month_studio import _fingerprint, _platform_packages, _scenes


ANGLE_LABELS = ("reveal", "mechanism", "myth_check", "sensory_pov", "survival_stakes")
SLOT_POLICY = (
    ("08:30", "quick_reveal", "efficient"),
    ("12:30", "myth_or_comparison", "hybrid"),
    ("18:30", "premium_hero", "premium"),
    ("22:00", "behavior_or_mechanism", "hybrid"),
)


def _angle(base: dict[str, Any], angle: str) -> dict[str, str]:
    title, concept = base["title"], base["concept"]
    subject = title.removeprefix("The ").removeprefix("Why ").removeprefix("How ")
    treatments = {
        "reveal": {
            "title": title,
            "hook": f"Watch closely: {subject.lower()} hides a detail most people miss.",
            "setup": concept,
            "truth": f"The visible behavior is evidence; the explanation must follow the measurable mechanism behind it.",
            "payoff": "The reveal works because the final image proves the opening claim.",
        },
        "mechanism": {
            "title": f"Inside the mechanism: {subject}",
            "hook": f"The impressive part is not what {subject.lower()} does—it is how the body makes it possible.",
            "setup": f"Slow the action down, isolate the relevant anatomy, and test this explanation: {concept}",
            "truth": "Move from observable action to anatomy, force, signal, or airflow without inventing an invisible step.",
            "payoff": "Now replay the real action: the mechanism is visible once you know where to look.",
        },
        "myth_check": {
            "title": f"Myth check: {subject}",
            "hook": f"The viral version of {subject.lower()} leaves out the most important limitation.",
            "setup": f"Put the popular claim beside the narrower evidence: {concept}",
            "truth": "Label what is observed, what is supported, and what remains an exaggeration or species-dependent claim.",
            "payoff": "The accurate version is still extraordinary—and safer to publish than the myth.",
        },
        "sensory_pov": {
            "title": f"What it senses: {subject}",
            "hook": f"For a moment, experience {subject.lower()} through the animal's available signals instead of human vision alone.",
            "setup": f"Translate the relevant sound, pressure, heat, light, motion, or chemical cue without claiming a literal first-person view. {concept}",
            "truth": "The visualization is an explanatory model; captions must distinguish measured input from artistic interpretation.",
            "payoff": "The same scene changes when the animal's real sensory channel becomes visible.",
        },
        "survival_stakes": {
            "title": f"Survival test: {subject}",
            "hook": f"One missed signal can decide whether {subject.lower()} ends in escape, feeding, or failure.",
            "setup": f"Stage one continuous, non-graphic survival problem around this documented behavior: {concept}",
            "truth": "Show the trade-off and its limits; do not imply every attempt succeeds or every individual behaves identically.",
            "payoff": "The adaptation creates an advantage, not a guarantee—and that uncertainty keeps the story alive.",
        },
    }
    return treatments[angle]


def expand_rawr_config(config: dict[str, Any], *, target: int = 120) -> dict[str, Any]:
    """Return a bootstrap-compatible config with exactly ``target`` Rawr ideas."""
    result = copy.deepcopy(config)
    brand = next(item for item in result["brands"] if item["slug"] == "rawr-nation")
    source = list(brand["ideas"])
    start = date.fromisoformat(result["month_start"])
    ideas: list[dict[str, Any]] = []
    for index in range(target):
        base = source[index % len(source)]
        angle = ANGLE_LABELS[(index // len(source)) % len(ANGLE_LABELS)]
        treatment = _angle(base, angle)
        day = index // 4
        slot = index % 4
        clock, slot_name, tier = SLOT_POLICY[slot]
        ideas.append({
            "scheduled_for": (start + timedelta(days=day)).isoformat(),
            "scheduled_time_local": clock,
            "title": treatment["title"],
            "concept": treatment["setup"],
            "format_name": "vertical_feature" if tier == "premium" else "vertical_short",
            "pillar": base["pillar"],
            "editorial_angle": angle,
            "daily_slot": slot_name,
            "production_tier": tier,
            "source_title": base["title"],
        })
    brand["monthly_target"] = target
    brand["metadata"]["cadence"] = "4 original Facebook-first videos daily; capacity 8 daily after analytics approval"
    brand["ideas"] = ideas
    return result


def build_high_volume_studio(base_studio: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    expanded = expand_rawr_config(config)
    brand = next(item for item in expanded["brands"] if item["slug"] == "rawr-nation")
    base_by_title = {item["title"]: item for item in base_studio["items"]}
    items: list[dict[str, Any]] = []
    for index, idea in enumerate(brand["ideas"], 1):
        base = base_by_title[idea["source_title"]]
        treatment = _angle(base, idea["editorial_angle"])
        feature = idea["production_tier"] == "premium"
        scenes = _scenes(
            hook=treatment["hook"], setup=treatment["setup"], concept=base["concept"],
            truth=treatment["truth"], payoff=treatment["payoff"], feature=feature,
        )
        narration = " ".join(scene["narration"] for scene in scenes)
        item = copy.deepcopy(base)
        item.update({
            "id": f"rawr-nation-{expanded['month_start']}-{index:03d}",
            "scheduled_for": idea["scheduled_for"], "scheduled_time_local": idea["scheduled_time_local"],
            "title": treatment["title"], "concept": treatment["setup"],
            "format": idea["format_name"], "batch": ((index - 1) // 20) + 1,
            "daily_slot": idea["daily_slot"], "editorial_angle": idea["editorial_angle"],
            "production_tier": idea["production_tier"], "source_title": idea["source_title"],
            "duration_seconds": scenes[-1]["end_seconds"], "scene_plan": scenes,
            "workflow_stage": "preview_queue" if index <= 6 else "script_review",
        })
        item["script"] = {
            "hook": treatment["hook"], "narration": narration, "payoff": treatment["payoff"],
            "word_count": len(narration.split()), "fact_review_required": True,
            "fact_status": base["script"]["fact_status"], "sources": base["script"]["sources"],
            "source_scope_note": "Sources support the base subject; this treatment requires a human claim-by-claim check.",
        }
        item["platform_packages"] = _platform_packages(item["title"], treatment["hook"], treatment["payoff"], item["pillar"])
        item["content_fingerprint"] = _fingerprint({"brand": "rawr-nation", "title": item["title"], "narration": narration})
        items.append(item)
    return {
        "schema_version": "p81.high_volume_calendar.v1", "brand": base_studio["brand"],
        "month_start": expanded["month_start"], "coverage_days": 30,
        "cadence_policy": {"baseline_per_day": 4, "capacity_per_day": 8, "timezone": "Asia/Karachi", "slots": [dict(time=x[0], purpose=x[1], tier=x[2]) for x in SLOT_POLICY]},
        "storage_policy": {"database": "metadata, scripts, approvals, schedules, checksums, analytics", "media": "local filesystem through content:// locators", "database_blobs": False},
        "items": items,
        "summary": {"masters": len(items), "days": 30, "daily_baseline": 4, "facebook_packages": len(items), "youtube_shorts_packages": len(items), "tiktok_packages": len(items), "platform_exports": len(items) * 3, "paid_jobs_started": 0, "publish_jobs_started": 0},
    }
