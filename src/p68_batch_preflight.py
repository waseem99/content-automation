"""Offline preflight for the remaining P68 RN natural-video batch."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.p68_job_state import atomic_write_json, utc_now
from src.p68_scientific_animation import RENDERERS


PREFLIGHT_VERSION = "p68.rn_batch_preflight.v1"
DEPLOY_KEYS = (
    "COMFYUI_REF",
    "WAN22_REVISION",
    "WAN21_REVISION",
    "RN_MODEL_DIR",
    "RN_OUTPUT_DIR",
    "RN_INPUT_DIR",
)
SUBMIT_KEYS = ("P68_RN_BASE_URL", "P68_RN_GPU_HOURLY_USD")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _configuration(keys: tuple[str, ...], environ: Mapping[str, str]) -> dict[str, bool]:
    return {key: bool(str(environ.get(key) or "").strip()) for key in keys}


def build_batch_preflight(
    pilots_root: Path,
    artifact_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    deploy = _configuration(DEPLOY_KEYS, env)
    submit = _configuration(SUBMIT_KEYS, env)
    pilots = []
    total_variants = 0
    for pilot_dir in sorted(path.parent for path in pilots_root.glob("*/content-plan.json")):
        plan = _load(pilot_dir / "content-plan.json")
        artifact_dir = artifact_root / "gold" / plan["pilot_id"]
        manifest_path = artifact_dir / "assets" / "asset-manifest.json"
        assets = {item["shot_id"]: item for item in _load(manifest_path)["assets"]}
        science_ids = {
            shot_id
            for candidate_pilot, shot_id in RENDERERS
            if candidate_pilot == plan["pilot_id"]
        }
        ready, blocked, authored = [], [], []
        for shot in plan["shots"]:
            shot_id = shot["shot_id"]
            if shot_id in science_ids:
                authored.append(shot_id)
                continue
            asset = assets[shot_id]
            variants = 2 if shot["story_stage"] in {"hook", "reveal"} else 1
            record = {
                "shot_id": shot_id,
                "story_stage": shot["story_stage"],
                "variants": variants,
                "keyframe_path": asset["path"],
                "keyframe_source": asset["source"],
            }
            if asset["source"] == "continuity_master_preview_fallback":
                blocked.append({**record, "reason": "purpose_built_keyframe_required"})
            else:
                ready.append(record)
                total_variants += variants
        ready_ids = ",".join(item["shot_id"] for item in ready)
        pilots.append(
            {
                "pilot_id": plan["pilot_id"],
                "ready": ready,
                "blocked": blocked,
                "authored_science_shot_ids": sorted(authored),
                "submit_command": (
                    "PYTHONPATH=. python scripts/p68_generate_clips.py submit "
                    f"--pilot {plan['pilot_id']} --shots {ready_ids}"
                    if ready_ids
                    else None
                ),
            }
        )
    missing_deploy = [key for key, present in deploy.items() if not present]
    missing_submit = [key for key, present in submit.items() if not present]
    payload = {
        "schema_version": PREFLIGHT_VERSION,
        "created_at": utc_now(),
        "configuration_presence": {
            "worker_deploy": deploy,
            "application_submit": submit,
        },
        "missing_worker_deploy_keys": missing_deploy,
        "missing_application_submit_keys": missing_submit,
        "worker_deploy_ready": not missing_deploy,
        "application_submit_ready": not missing_submit,
        "pilots": pilots,
        "ready_variant_count": total_variants,
        "paid_provider_calls_planned": 0,
        "publish_allowed": False,
    }
    return payload


def write_batch_preflight(
    pilots_root: Path,
    artifact_root: Path,
    output_path: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    payload = build_batch_preflight(pilots_root, artifact_root, environ=environ)
    atomic_write_json(output_path, payload)
    return {**payload, "preflight_path": str(output_path)}
