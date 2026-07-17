"""Build an honest, local-first production queue for the four priority brands."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PRIORITY_BRANDS = ("rawr-nation", "animal-x", "historiq", "ani-films")
BRAND_PROFILES = {"rawr_nation": "rawr-nation", "animal_x": "animal-x"}
REQUIRED_PILOT_FILES = (
    "source-brief.json", "content-plan.json", "storyboard.json", "voice-project.json", "captions.srt",
)


def _tokens(value: str) -> set[str]:
    stop = {"a", "an", "and", "how", "in", "is", "of", "the", "to", "what", "why", "with"}
    return {word for word in re.findall(r"[a-z0-9]+", value.lower()) if word not in stop and len(word) > 2}


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / max(len(a | b), 1)


def discover_pilots(pilots_root: Path, artifacts_root: Path) -> list[dict[str, Any]]:
    pilots: list[dict[str, Any]] = []
    if not pilots_root.exists():
        return pilots
    for directory in sorted(path for path in pilots_root.iterdir() if path.is_dir()):
        brief_path = directory / "source-brief.json"
        if not brief_path.is_file():
            continue
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        brand_slug = BRAND_PROFILES.get(str(brief.get("brand_profile", "")))
        if not brand_slug:
            continue
        artifact = artifacts_root / "gold" / directory.name
        narrations = sorted((artifact / "narration").glob("*.wav")) if artifact.exists() else []
        previews = sorted((artifact / "renders").glob("*/final_review.mp4")) if artifact.exists() else []
        pilots.append({
            "pilot_id": directory.name,
            "brand_slug": brand_slug,
            "topic": str(brief.get("topic", "")),
            "pack_complete": all((directory / name).is_file() for name in REQUIRED_PILOT_FILES),
            "narration_ready": bool(narrations),
            "preview_ready": bool(previews),
            "preview_path": str(previews[-1]) if previews else None,
        })
    return pilots


def _match_pilot(brand_slug: str, idea: dict[str, Any], pilots: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [pilot for pilot in pilots if pilot["brand_slug"] == brand_slug]
    subject = f'{idea.get("title", "")} {idea.get("concept", "")}'
    scored = sorted(((_similarity(subject, pilot["topic"]), pilot) for pilot in candidates), reverse=True, key=lambda row: row[0])
    return scored[0][1] if scored and scored[0][0] >= 0.15 else None


def _production_stage(pilot: dict[str, Any] | None) -> str:
    if pilot and pilot["preview_ready"]:
        return "preview"
    if pilot and pilot["narration_ready"]:
        return "preview_build"
    if pilot and pilot["pack_complete"]:
        return "script"
    return "idea"


def _next_action(stage: str) -> str:
    return {
        "idea": "research_and_build_script_pack",
        "script": "human_review_script_and_scene_plan",
        "preview_build": "assemble_free_review_preview",
        "preview": "human_review_before_paid_render",
    }[stage]


def build_month_factory(config: dict[str, Any], *, pilots_root: Path, artifacts_root: Path, batch_size: int = 6) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    by_slug = {brand["slug"]: brand for brand in config.get("brands", [])}
    missing = [slug for slug in PRIORITY_BRANDS if slug not in by_slug]
    if missing:
        raise ValueError(f"Priority brands missing from configuration: {', '.join(missing)}")
    pilots = discover_pilots(pilots_root, artifacts_root)
    brands, items = [], []
    for slug in PRIORITY_BRANDS:
        brand = by_slug[slug]
        ideas = list(brand.get("ideas") or [])
        onboarding = str((brand.get("metadata") or {}).get("onboarding_status", "unknown"))
        blocker = None if ideas else "account_brief_and_reference_review_required"
        brands.append({
            "id": slug, "name": brand["display_name"], "niche": brand["niche"],
            "kind": brand["content_mode"], "cadence": (brand.get("metadata") or {}).get("cadence", ""),
            "monthlyTarget": int(brand["monthly_target"]), "primary": str(brand["primary_platform"]).title(),
            "pillars": brand.get("content_pillars", []), "onboardingStatus": onboarding,
            "conceptCount": len(ideas), "blocker": blocker,
        })
        for index, idea in enumerate(ideas, start=1):
            pilot = _match_pilot(slug, idea, pilots)
            stage = _production_stage(pilot)
            items.append({
                "id": f"{slug}-{config['month_start']}-{index:02d}",
                "date": idea["scheduled_for"], "brand": slug, "title": idea["title"],
                "concept": idea["concept"], "format": idea["format_name"], "pillar": idea["pillar"],
                "stage": stage, "batch": ((index - 1) // batch_size) + 1,
                "pilotId": pilot["pilot_id"] if pilot else None,
                "previewPath": pilot["preview_path"] if pilot else None,
                "nextAction": _next_action(stage),
                "assets": [
                    "concept",
                    *( ["script pack"] if pilot and pilot["pack_complete"] else [] ),
                    *( ["VO"] if pilot and pilot["narration_ready"] else [] ),
                    *( ["preview"] if pilot and pilot["preview_ready"] else [] ),
                ],
            })
    stage_counts: dict[str, int] = {}
    for item in items:
        stage_counts[item["stage"]] = stage_counts.get(item["stage"], 0) + 1
    return {
        "schema_version": "p79.month_factory.v1", "month_start": config["month_start"],
        "priority_brand_count": len(PRIORITY_BRANDS), "batch_size": batch_size,
        "brands": brands, "items": items,
        "summary": {
            "monthly_target": sum(brand["monthlyTarget"] for brand in brands),
            "concepts_ready": len(items), "brands_with_complete_inventory": sum(brand["conceptCount"] >= brand["monthlyTarget"] for brand in brands),
            "brands_blocked_for_brief": sum(bool(brand["blocker"]) for brand in brands),
            "stage_counts": stage_counts, "paid_render_jobs_started": 0, "publish_jobs_started": 0,
        },
        "guardrails": {"human_approval_before_paid_render": True, "human_approval_before_publish": True, "vercel_deployment_performed": False},
    }
