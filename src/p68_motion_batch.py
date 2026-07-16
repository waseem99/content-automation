"""Offline natural-motion inventory and routing for the six P68 pilots.

Planning is intentionally side-effect free: it never submits provider jobs,
spends money, deploys infrastructure, or marks media as approved.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from src.p68_job_state import atomic_write_json
from src.p68_pilot_batch import EXPECTED_PILOT_IDS
from src.p68_scientific_animation import RENDERERS


MOTION_BATCH_VERSION = "p68.motion_batch_plan.v1"
HERO_STAGES = {"hook", "reveal", "payoff"}
REQUIRED_ENV = ("P68_RN_BASE_URL", "P68_RN_GPU_HOURLY_USD")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assets(artifact_dir: Path) -> dict[str, dict[str, Any]]:
    path = artifact_dir / "assets" / "asset-manifest.json"
    if not path.is_file():
        return {}
    return {str(item["shot_id"]): item for item in _load(path).get("assets") or []}


def _authored_clip(artifact_dir: Path, shot_id: str) -> Path | None:
    candidates = sorted((artifact_dir / "clips").glob(f"scientific-v*/{shot_id}.mp4"))
    return candidates[-1] if candidates else None


def build_motion_batch_plan(
    pilots_root: str | Path,
    artifact_root: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
    standard_variants: int = 1,
    hero_variants: int = 2,
    estimated_runtime_seconds_per_variant: Decimal = Decimal("540"),
) -> dict[str, Any]:
    if standard_variants < 1 or hero_variants < standard_variants:
        raise ValueError("variant counts must be positive and hero variants cannot be lower")
    if estimated_runtime_seconds_per_variant <= 0:
        raise ValueError("estimated runtime must be positive")
    env = environ or {}
    env_presence = {key: bool(str(env.get(key) or "").strip()) for key in REQUIRED_ENV}
    try:
        hourly = Decimal(str(env.get("P68_RN_GPU_HOURLY_USD") or "0"))
    except Exception as exc:  # noqa: BLE001 - produce a clear configuration error
        raise ValueError("P68_RN_GPU_HOURLY_USD must be a decimal") from exc
    if hourly < 0:
        raise ValueError("P68_RN_GPU_HOURLY_USD cannot be negative")

    pilots: list[dict[str, Any]] = []
    total_variants = 0
    natural_shots = 0
    authored_shots = 0
    ready_shots = 0
    blocked_shots = 0
    for plan_path in sorted(Path(pilots_root).glob("*/content-plan.json")):
        plan = _load(plan_path)
        pilot_id = str(plan["pilot_id"])
        artifact_dir = Path(artifact_root) / "gold" / pilot_id
        assets = _assets(artifact_dir)
        shots: list[dict[str, Any]] = []
        for shot in plan.get("shots") or []:
            shot_id = str(shot["shot_id"])
            authored = (pilot_id, shot_id) in RENDERERS
            variants = 0 if authored else hero_variants if shot.get("story_stage") in HERO_STAGES else standard_variants
            duration = Decimal(str(shot.get("duration_seconds") or "0")) + Decimal(
                str(shot.get("transition_handle_seconds") or "0.5")
            )
            if authored:
                authored_shots += 1
                clip = _authored_clip(artifact_dir, shot_id)
                status = "authored_ready" if clip else "authored_render_required"
                route = "deterministic_scientific_animation"
                keyframe = None
            else:
                natural_shots += 1
                total_variants += variants
                asset = assets.get(shot_id)
                keyframe = str(asset.get("path")) if asset else None
                acceptable = bool(
                    asset
                    and asset.get("source") != "continuity_master_preview_fallback"
                    and Path(str(asset.get("path") or "")).is_file()
                )
                if acceptable:
                    ready_shots += 1
                    status = "ready_for_rn_generation"
                else:
                    blocked_shots += 1
                    status = "shot_specific_keyframe_required"
                route = "rn_wan_open_source_first"
            shots.append(
                {
                    "shot_id": shot_id,
                    "story_stage": shot.get("story_stage"),
                    "planned_clip_seconds": float(duration),
                    "route": route,
                    "variant_count": variants,
                    "keyframe_path": keyframe,
                    "status": status,
                    "premium_escalation": {
                        "allowed_automatically": False,
                        "trigger": "two_reviewed_rn_variants_fail_motion_or_continuity",
                        "scope": "single_failed_shot_only",
                        "human_spend_approval_required": True,
                    },
                    "natural_motion_ready": False,
                    "production_candidate": False,
                    "publish_allowed": False,
                }
            )
        pilots.append(
            {
                "pilot_id": pilot_id,
                "brand_profile": plan.get("brand_profile"),
                "shots": shots,
                "natural_motion_ready": False,
                "production_candidate": False,
                "publish_allowed": False,
            }
        )

    roster = {item["pilot_id"] for item in pilots}
    runtime_seconds = estimated_runtime_seconds_per_variant * total_variants
    estimated_cost = (runtime_seconds / Decimal("3600") * hourly).quantize(Decimal("0.0001"))
    configuration_ready = all(env_presence.values()) and hourly > 0
    return {
        "schema_version": MOTION_BATCH_VERSION,
        "pilot_count": len(pilots),
        "roster_complete": roster == EXPECTED_PILOT_IDS,
        "pilots": pilots,
        "inventory": {
            "total_shots": natural_shots + authored_shots,
            "authored_science_shots": authored_shots,
            "natural_motion_shots": natural_shots,
            "natural_shots_with_keyframes": ready_shots,
            "natural_shots_blocked_on_keyframes": blocked_shots,
            "planned_generation_variants": total_variants,
        },
        "configuration_presence": env_presence,
        "rn_configuration_ready": configuration_ready,
        "estimated_runtime_seconds": str(runtime_seconds),
        "estimated_rn_cost_usd": str(estimated_cost),
        "estimate_is_not_authorization": True,
        "execution_allowed": bool(configuration_ready and ready_shots and roster == EXPECTED_PILOT_IDS),
        "next_gate": (
            "create_shot_specific_keyframes"
            if blocked_shots
            else "render_missing_authored_shots_and_submit_bounded_rn_batch"
        ),
        "premium_provider_calls_allowed": False,
        "paid_provider_calls_made": 0,
        "vercel_deployment_required": False,
        "production_candidate_count": 0,
        "publish_allowed": False,
    }


def write_motion_batch_plan(
    pilots_root: str | Path,
    artifact_root: str | Path,
    output_path: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    result = build_motion_batch_plan(pilots_root, artifact_root, **kwargs)
    atomic_write_json(Path(output_path), result)
    return result
