"""Deterministic completion audit for the six P68 benchmark pilots.

The audit is intentionally side-effect free. It inventories planning, keyframes,
authored science clips, generated candidates, selected clips, and hybrid review
renders without contacting a provider, spending money, deploying infrastructure,
or granting publication approval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.p68_job_state import atomic_write_json
from src.p68_keyframe_batch import build_keyframe_work_orders
from src.p68_motion_batch import build_motion_batch_plan
from src.p68_pilot_batch import EXPECTED_PILOT_IDS, evaluate_spec_batch
from src.p68_scientific_animation import RENDERERS


AUDIT_VERSION = "p68.completion_audit.v1"
KEYFRAME_CONFIGURATION_KEYS = (
    "P68_KEYFRAME_CHECKPOINT",
    "P68_KEYFRAME_MODEL_LICENSE_TYPE",
    "P68_KEYFRAME_MODEL_LICENSE_URL",
    "P68_RN_GPU_HOURLY_USD",
)


def _load(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def _existing_media_shots(path: Path, field: str) -> set[str]:
    payload = _load(path)
    result: set[str] = set()
    for item in payload.get(field) or []:
        media_path = Path(str(item.get("path") or ""))
        if media_path.is_file() and media_path.stat().st_size > 0:
            result.add(str(item.get("shot_id") or ""))
    return {item for item in result if item}


def _hybrid_render_ready(artifact_dir: Path) -> bool:
    manifest = _load(artifact_dir / "renders" / "hybrid-v1" / "render_manifest.json")
    output = Path(str(manifest.get("output_path") or ""))
    return bool(manifest.get("is_valid") and output.is_file() and output.stat().st_size > 0)


def _keyframe_configuration(environ: Mapping[str, str]) -> dict[str, bool]:
    base_url = bool(
        str(environ.get("P68_KEYFRAME_BASE_URL") or "").strip()
        or str(environ.get("P68_RN_BASE_URL") or "").strip()
    )
    values = {key: bool(str(environ.get(key) or "").strip()) for key in KEYFRAME_CONFIGURATION_KEYS}
    return {"P68_KEYFRAME_BASE_URL_OR_P68_RN_BASE_URL": base_url, **values}


def _queue_command(action: str, pilot_id: str, shot_id: str | None = None) -> str | None:
    if action == "render_authored_science":
        return f"PYTHONPATH=. python scripts/p68_render_science.py --pilot {pilot_id}"
    if action == "create_or_source_keyframe" and shot_id:
        return (
            "PYTHONPATH=. python scripts/p68_generate_keyframes.py submit "
            f"--pilot {pilot_id} --shots {shot_id} --limit 1"
        )
    if action == "review_keyframe" and shot_id:
        return (
            "PYTHONPATH=. python scripts/p68_keyframes.py approve "
            f"--pilot {pilot_id} --shot {shot_id} --reviewer <name> --note <evidence>"
        )
    if action == "submit_bounded_rn_generation" and shot_id:
        return (
            "PYTHONPATH=. python scripts/p68_generate_clips.py submit "
            f"--pilot {pilot_id} --shots {shot_id}"
        )
    if action == "review_and_select_candidate" and shot_id:
        return (
            "PYTHONPATH=. python scripts/p68_select_clips.py "
            f"--pilot {pilot_id} --select {shot_id}=<variant> --reviewer <name> --note <evidence>"
        )
    if action == "assemble_hybrid_review":
        return f"PYTHONPATH=. python scripts/p68_build_hybrid_reviews.py --pilot {pilot_id}"
    return None


def build_completion_audit(
    pilots_root: str | Path,
    artifact_root: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build one honest execution view across all six P68 pilots."""

    env = environ or {}
    pilots_path = Path(pilots_root)
    artifacts_path = Path(artifact_root)
    spec = evaluate_spec_batch(pilots_path)
    keyframes = build_keyframe_work_orders(pilots_path, artifacts_path)
    motion = build_motion_batch_plan(pilots_path, artifacts_path, environ=env)

    spec_by_pilot = {str(item["pilot_id"]): item for item in spec["pilots"]}
    keyframes_by_pilot = {
        str(item["pilot_id"]): {str(order["shot_id"]): order for order in item["orders"]}
        for item in keyframes["pilots"]
    }
    motion_by_pilot = {
        str(item["pilot_id"]): {str(shot["shot_id"]): shot for shot in item["shots"]}
        for item in motion["pilots"]
    }

    keyframe_configuration = _keyframe_configuration(env)
    keyframe_generation_ready = all(keyframe_configuration.values())
    rn_configuration_ready = bool(motion["rn_configuration_ready"])

    queue: list[dict[str, Any]] = []
    pilot_rows: list[dict[str, Any]] = []
    totals = {
        "total_shots": 0,
        "authored_science_shots": 0,
        "authored_science_ready": 0,
        "natural_motion_shots": 0,
        "keyframes_approved": 0,
        "keyframes_pending_review": 0,
        "keyframes_missing": 0,
        "candidate_shots_available": 0,
        "selected_natural_shots": 0,
        "hybrid_review_renders_ready": 0,
    }

    for plan_path in sorted(pilots_path.glob("*/content-plan.json")):
        plan = _load(plan_path)
        pilot_id = str(plan["pilot_id"])
        artifact_dir = artifacts_path / "gold" / pilot_id
        selected_shots = _existing_media_shots(
            artifact_dir / "clips" / "generated" / "selection-manifest.json",
            "selected_clips",
        )
        candidate_shots = _existing_media_shots(
            artifact_dir / "clips" / "generated" / "candidate-manifest.json",
            "candidates",
        )
        render_ready = _hybrid_render_ready(artifact_dir)
        shots: list[dict[str, Any]] = []

        for shot in plan.get("shots") or []:
            shot_id = str(shot["shot_id"])
            totals["total_shots"] += 1
            authored = (pilot_id, shot_id) in RENDERERS
            action: str | None = None
            status: str

            if authored:
                totals["authored_science_shots"] += 1
                motion_record = motion_by_pilot[pilot_id][shot_id]
                if motion_record["status"] == "authored_ready":
                    totals["authored_science_ready"] += 1
                    status = "ready_for_assembly"
                else:
                    status = "authored_science_render_required"
                    action = "render_authored_science"
            else:
                totals["natural_motion_shots"] += 1
                order = keyframes_by_pilot[pilot_id][shot_id]
                if shot_id in selected_shots:
                    totals["selected_natural_shots"] += 1
                    status = "ready_for_assembly"
                elif shot_id in candidate_shots:
                    totals["candidate_shots_available"] += 1
                    status = "candidate_review_required"
                    action = "review_and_select_candidate"
                elif order["ready_for_video_generation"]:
                    totals["keyframes_approved"] += 1
                    if rn_configuration_ready:
                        status = "approved_keyframe_ready_for_rn"
                        action = "submit_bounded_rn_generation"
                    else:
                        status = "approved_keyframe_waiting_for_rn_configuration"
                        action = "configure_private_rn_worker"
                elif order["human_review_status"] == "pending_keyframe_review":
                    totals["keyframes_pending_review"] += 1
                    status = "keyframe_review_required"
                    action = "review_keyframe"
                else:
                    totals["keyframes_missing"] += 1
                    status = "shot_specific_keyframe_required"
                    action = "create_or_source_keyframe"

            record = {
                "pilot_id": pilot_id,
                "brand_profile": plan.get("brand_profile"),
                "shot_id": shot_id,
                "story_stage": shot.get("story_stage"),
                "route": "deterministic_scientific_animation" if authored else "rn_wan_open_source_first",
                "status": status,
                "next_action": action,
                "command": _queue_command(action or "", pilot_id, shot_id),
                "production_candidate": False,
                "publish_allowed": False,
            }
            shots.append(record)
            if action:
                queue.append(record)

        all_shots_ready = all(item["status"] == "ready_for_assembly" for item in shots)
        if render_ready:
            totals["hybrid_review_renders_ready"] += 1
            pilot_next_action = "complete_human_benchmark_review"
        elif all_shots_ready:
            pilot_next_action = "assemble_hybrid_review"
            queue.append(
                {
                    "pilot_id": pilot_id,
                    "brand_profile": plan.get("brand_profile"),
                    "shot_id": None,
                    "story_stage": None,
                    "route": "hybrid_review_assembly",
                    "status": "all_shots_ready_for_assembly",
                    "next_action": pilot_next_action,
                    "command": _queue_command(pilot_next_action, pilot_id),
                    "production_candidate": False,
                    "publish_allowed": False,
                }
            )
        else:
            pilot_next_action = next(
                (item["next_action"] for item in shots if item["next_action"]),
                "repair_pilot_artifacts",
            )

        pilot_rows.append(
            {
                "pilot_id": pilot_id,
                "brand_profile": plan.get("brand_profile"),
                "spec_ready": bool(spec_by_pilot[pilot_id]["spec_ready"]),
                "shots": shots,
                "all_shots_ready_for_assembly": all_shots_ready,
                "hybrid_review_render_ready": render_ready,
                "next_action": pilot_next_action,
                "production_candidate": False,
                "publish_allowed": False,
            }
        )

    if not spec["all_specs_ready"]:
        next_gate = "repair_six_pilot_specs"
    elif totals["keyframes_missing"] or totals["keyframes_pending_review"]:
        next_gate = "create_and_review_shot_specific_keyframes"
    elif totals["authored_science_ready"] < totals["authored_science_shots"]:
        next_gate = "render_authored_science_clips"
    elif totals["keyframes_approved"] and not rn_configuration_ready:
        next_gate = "configure_private_rn_worker"
    elif totals["selected_natural_shots"] < totals["natural_motion_shots"]:
        next_gate = "generate_review_and_select_natural_motion"
    elif totals["hybrid_review_renders_ready"] < len(pilot_rows):
        next_gate = "assemble_hybrid_review_videos"
    else:
        next_gate = "complete_human_benchmark_and_closeout_review"

    roster_complete = {item["pilot_id"] for item in pilot_rows} == EXPECTED_PILOT_IDS
    return {
        "schema_version": AUDIT_VERSION,
        "pilot_count": len(pilot_rows),
        "roster_complete": roster_complete,
        "specs_ready": bool(spec["all_specs_ready"]),
        "keyframe_generation_configuration_presence": keyframe_configuration,
        "keyframe_generation_configuration_ready": keyframe_generation_ready,
        "rn_configuration_presence": motion["configuration_presence"],
        "rn_configuration_ready": rn_configuration_ready,
        "totals": totals,
        "pilots": pilot_rows,
        "execution_queue": queue,
        "next_gate": next_gate,
        "external_execution_required": bool(
            totals["natural_motion_shots"] > totals["selected_natural_shots"]
        ),
        "provider_calls_made": 0,
        "paid_provider_calls_made": 0,
        "vercel_deployment_required": False,
        "human_review_required": True,
        "production_candidate_count": 0,
        "publish_allowed": False,
    }


def write_completion_audit(
    pilots_root: str | Path,
    artifact_root: str | Path,
    output_path: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    result = build_completion_audit(pilots_root, artifact_root, environ=environ)
    path = Path(output_path)
    atomic_write_json(path, result)

    report_path = path.with_suffix(".md")
    rows = "\n".join(
        f"| {pilot['pilot_id']} | {pilot['brand_profile']} | "
        f"{'yes' if pilot['spec_ready'] else 'no'} | "
        f"{'yes' if pilot['all_shots_ready_for_assembly'] else 'no'} | "
        f"{'yes' if pilot['hybrid_review_render_ready'] else 'no'} | "
        f"{pilot['next_action']} |"
        for pilot in result["pilots"]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# P68 Six-Pilot Completion Audit\n\n"
        f"Next gate: `{result['next_gate']}`\n\n"
        "| Pilot | Brand | Spec ready | Shots ready | Review render | Next action |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{rows}\n\n"
        f"Execution queue items: **{len(result['execution_queue'])}**\n\n"
        "No provider calls, paid rendering, Vercel deployment, publication, or final approval were performed.\n",
        encoding="utf-8",
    )
    return {**result, "json_path": str(path), "report_path": str(report_path)}
