from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.video_pilot.grouped_service import GroupedVideoPilotService
from src.application.video_pilot.models import (
    PilotCaseCreateRequest,
    PilotItemCreateRequest,
    PilotRunCreateRequest,
    PilotRunStartRequest,
)
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.p113_model_policy_onboarding import onboard as onboard_model_policies


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / "config" / "p113-pilot-plan.example.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"JSON file was not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON file is invalid: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return payload


def _snapshot_parts(path: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if path is None:
        return {}, {}
    snapshot = _load_json(path)
    hardware = dict(snapshot.get("workstation") or {})
    software = dict(snapshot.get("software") or {})
    hardware["snapshot_kind"] = snapshot.get("snapshot_kind")
    hardware["snapshot_generated_at"] = snapshot.get("generated_at")
    return hardware, software


def initialize(*, plan_path: Path, hardware_snapshot_path: Path | None) -> dict[str, Any]:
    plan = _load_json(plan_path)
    hardware_snapshot, software_snapshot = _snapshot_parts(hardware_snapshot_path)
    actor = os.getenv("LOCAL_SUPER_ADMIN_OPERATOR_ID", "local-super-admin")

    policy_result = onboard_model_policies()
    database = Database(get_database_settings())
    database.open(require_schema=True)
    service = GroupedVideoPilotService(database)
    created_items = 0
    created_cases = 0
    try:
        with database.connection() as conn:
            existing_run = conn.execute(
                "SELECT * FROM football_brief.video_pilot_runs WHERE run_key=%s",
                (str(plan["run_key"]),),
            ).fetchone()

        if existing_run:
            run = dict(existing_run)
            if int(run["target_videos"]) != int(plan.get("target_videos", 3)):
                raise RuntimeError("Existing P113 run has a different target_videos value")
            if int(run["target_attempts"]) != int(plan.get("target_attempts", 30)):
                raise RuntimeError("Existing P113 run has a different target_attempts value")
            run_reused = True
        else:
            created = service.create_run(
                PilotRunCreateRequest(
                    run_key=plan["run_key"],
                    title=plan["title"],
                    target_videos=plan.get("target_videos", 3),
                    target_attempts=plan.get("target_attempts", 30),
                    hardware_snapshot=hardware_snapshot,
                    software_snapshot=software_snapshot,
                    baseline_assumptions=plan.get("baseline_assumptions") or {},
                ),
                actor=actor,
            )
            run = created["run"]
            run_reused = False

        run_id = UUID(str(run["id"]))
        for item_spec in plan.get("items") or []:
            with database.connection() as conn:
                existing_item = conn.execute(
                    """SELECT * FROM football_brief.video_pilot_items
                       WHERE pilot_run_id=%s AND item_key=%s""",
                    (run_id, str(item_spec["item_key"])),
                ).fetchone()
            if existing_item:
                item = dict(existing_item)
            else:
                item = service.create_item(
                    run_id,
                    PilotItemCreateRequest(
                        item_key=item_spec["item_key"],
                        title=item_spec["title"],
                        portfolio_content_id=item_spec.get("portfolio_content_id"),
                        target_duration_seconds=item_spec.get("target_duration_seconds", 120),
                    ),
                    actor=actor,
                )["item"]
                created_items += 1

            item_id = UUID(str(item["id"]))
            for case_spec in item_spec.get("cases") or []:
                with database.connection() as conn:
                    existing_case = conn.execute(
                        """SELECT id FROM football_brief.video_pilot_cases
                           WHERE pilot_run_id=%s AND case_key=%s""",
                        (run_id, str(case_spec["case_key"])),
                    ).fetchone()
                if existing_case:
                    continue
                service.create_case(
                    run_id,
                    PilotCaseCreateRequest(
                        pilot_item_id=item_id,
                        case_key=case_spec["case_key"],
                        title=case_spec["title"],
                        shot_class=case_spec["shot_class"],
                        difficulty=case_spec["difficulty"],
                        distribution_scope=case_spec["distribution_scope"],
                        release_territories=tuple(case_spec.get("release_territories") or ()),
                        target_duration_seconds=case_spec["target_duration_seconds"],
                        prompt=case_spec["prompt"],
                        negative_prompt=case_spec.get("negative_prompt"),
                        input_asset_id=case_spec.get("input_asset_id"),
                        required_model_keys=tuple(case_spec.get("required_model_keys") or ()),
                        acceptance_criteria=case_spec.get("acceptance_criteria") or {},
                    ),
                    actor=actor,
                )
                created_cases += 1

        with database.connection() as conn:
            current = conn.execute(
                "SELECT status FROM football_brief.video_pilot_runs WHERE id=%s",
                (run_id,),
            ).fetchone()
        if current and current["status"] == "planned":
            service.start_run(
                run_id,
                PilotRunStartRequest(
                    hardware_snapshot=hardware_snapshot or None,
                    software_snapshot=software_snapshot or None,
                ),
                actor=actor,
            )

        detail = service.detail(run_id)
        return {
            "ok": True,
            "kind": "p113_pilot_initialized",
            "pilot_run_id": str(run_id),
            "run_key": plan["run_key"],
            "run_reused": run_reused,
            "created_items": created_items,
            "created_cases": created_cases,
            "total_items": len(detail["items"]),
            "total_cases": len(detail["cases"]),
            "target_videos": int(detail["run"]["target_videos"]),
            "target_attempts": int(detail["run"]["target_attempts"]),
            "model_policies": policy_result["policies"],
            "paid_generation_enabled": False,
            "automatic_public_publishing": False,
        }
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or resume the P113 measured dual-model pilot.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--hardware-snapshot", default=None)
    args = parser.parse_args()

    plan_path = Path(args.plan).expanduser().resolve()
    snapshot_path = Path(args.hardware_snapshot).expanduser().resolve() if args.hardware_snapshot else None
    result = initialize(plan_path=plan_path, hardware_snapshot_path=snapshot_path)
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
