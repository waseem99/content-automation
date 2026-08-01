from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import time
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from src.application.campaigns.models import CampaignCreateRequest, CampaignItemInput, CampaignItemsAddRequest
from src.application.campaigns.validated_service import ValidatedCampaignService
from src.application.mass_operations import MassOperationError, MassOperationService
from src.application.pre_generation.validated_service import ValidatedPreGenerationService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operator_api.access import OperatorAccessService


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _key() -> str:
    return datetime.now(timezone.utc).strftime("p130-%Y%m%dt%H%M%S%fz")


def _timed(timings: dict[str, float], key: str, function, *args, **kwargs):
    started = time.perf_counter()
    result = function(*args, **kwargs)
    timings[key] = round((time.perf_counter() - started) * 1000, 3)
    return result


def _items(count: int, *, primary_platform: str) -> list[CampaignItemInput]:
    return [
        CampaignItemInput(
            item_key=f"mass-{ordinal:04d}",
            title=f"Mass operation acceptance item {ordinal:04d}",
            topic=f"Database-native grouped exception item {ordinal:04d}",
            objective="Prove exact background mass-operation results.",
            audience="Internal acceptance benchmark",
            format_name="master_video",
            primary_platform=primary_platform,
            target_platforms=[primary_platform],
            target_duration_seconds=45,
            short_cut_count=0,
            language="en-US",
            scheduled_for=date(2026, 8, 3),
            priority=50,
            metadata={"p130_acceptance": True, "ordinal": ordinal},
        )
        for ordinal in range(1, count + 1)
    ]


def run_acceptance(
    *,
    items: int = 1_000,
    acceptance_key: str | None = None,
    actor: str = "local-admin",
) -> dict[str, Any]:
    if not 1_000 <= items <= 20_000:
        raise ValueError("items must be between 1,000 and 20,000")
    key = acceptance_key or _key()
    timings: dict[str, float] = {}
    database = Database(get_database_settings())
    database.open(require_schema=True)
    acceptance_id: UUID | None = None
    try:
        with database.transaction() as conn:
            operator = conn.execute(
                "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
                (actor,),
            ).fetchone()
            brands = conn.execute(
                """SELECT brand.id,brand.primary_platform
                   FROM football_brief.brands brand
                   JOIN football_brief.pre_generation_autopilot_policies policy
                     ON policy.brand_id=brand.id AND policy.active=true
                   WHERE brand.active=true ORDER BY brand.slug LIMIT 2"""
            ).fetchall()
            if operator is None or len(brands) < 2:
                raise RuntimeError("mass-operation onboarding requires an operator and two active brands")
            acceptance = conn.execute(
                """INSERT INTO football_brief.mass_operations_acceptance_runs
                   (acceptance_key,status,requested_items,requested_by,environment)
                   VALUES (%s,'running',%s,%s,%s::jsonb) RETURNING id""",
                (
                    key,
                    items,
                    actor,
                    _json({
                        "hostname": socket.gethostname(),
                        "platform": platform.platform(),
                        "python": platform.python_version(),
                        "git_sha": os.getenv("GITHUB_SHA") or os.getenv("OPS_GIT_SHA"),
                        "spreadsheet_dependency": False,
                        "public_roles": ["super_admin", "admin", "reviewer"],
                    }),
                ),
            ).fetchone()
            acceptance_id = UUID(str(acceptance["id"]))

        access = OperatorAccessService(database)
        assigned_operator = f"{key}-assigned"
        denied_operator = f"{key}-denied"
        _timed(
            timings,
            "create_assigned_reviewer",
            access.upsert_user,
            operator_id=assigned_operator,
            display_name="P130 Assigned Reviewer",
            active=True,
            roles=["reviewer"],
            brand_ids=[str(brands[0]["id"])],
            actor=actor,
        )
        _timed(
            timings,
            "create_denied_reviewer",
            access.upsert_user,
            operator_id=denied_operator,
            display_name="P130 Denied Reviewer",
            active=True,
            roles=["reviewer"],
            brand_ids=[str(brands[1]["id"])],
            actor=actor,
        )

        campaign_service = ValidatedCampaignService(database)
        created = _timed(
            timings,
            "create_campaign",
            campaign_service.create_campaign,
            CampaignCreateRequest(
                campaign_key=key,
                brand_id=UUID(str(brands[0]["id"])),
                name=f"P130 {items:,}-item Mass Operations Acceptance",
                description="Database-native selection and background action acceptance.",
                metadata={"p130_acceptance": True},
            ),
            actor=actor,
        )
        campaign_id = UUID(str(created["campaign"]["id"]))
        version_id = UUID(str(created["versions"][0]["id"]))
        payload = _timed(
            timings,
            "build_items",
            _items,
            items,
            primary_platform=str(brands[0]["primary_platform"]),
        )
        _timed(
            timings,
            "insert_items",
            campaign_service.add_items,
            campaign_version_id=version_id,
            request=CampaignItemsAddRequest(items=payload),
            actor=actor,
        )
        validation = _timed(
            timings,
            "validate_campaign",
            campaign_service.validate_version,
            campaign_version_id=version_id,
            actor=actor,
        )
        if not validation["ok"]:
            raise RuntimeError(f"campaign validation failed: {validation}")
        _timed(
            timings,
            "activate_campaign",
            campaign_service.activate_version,
            campaign_version_id=version_id,
            actor=actor,
        )
        pre = ValidatedPreGenerationService(database)
        ensured = pre.ensure_runs(campaign_id=campaign_id, actor=assigned_operator)
        if int(ensured["created"]) != items:
            raise RuntimeError(f"expected {items} runs, created {ensured['created']}")

        fingerprint = hashlib.sha256(f"{key}:grouped-system-failure".encode()).hexdigest()
        with database.transaction() as conn:
            rows = conn.execute(
                """SELECT item.id AS item_id,run.id AS run_id
                   FROM football_brief.production_campaign_items item
                   JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                   WHERE item.campaign_version_id=%s ORDER BY item.ordinal""",
                (version_id,),
            ).fetchall()
            item_ids = [row["item_id"] for row in rows]
            run_ids = [row["run_id"] for row in rows]
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET status='hard_block',current_stage='script_checks',
                       last_error_code='system_block',last_error_detail=%s::jsonb,
                       updated_at=now()
                   WHERE id=ANY(%s::uuid[])""",
                (_json({"p130_acceptance": True}), run_ids),
            )
            conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state='hard_block',disposition='hard_block',updated_at=now()
                   WHERE id=ANY(%s::uuid[])""",
                (item_ids,),
            )
            conn.executemany(
                """INSERT INTO football_brief.pre_generation_exceptions
                   (run_id,campaign_item_id,exception_code,category,severity,status,
                    rule_version,fingerprint,details)
                   VALUES (%s,%s,'system_block','system','hard_block','open',
                           'p130-v1',%s,%s::jsonb)""",
                [
                    (row["run_id"], row["item_id"], fingerprint, _json({"p130_acceptance": True}))
                    for row in rows
                ],
            )

        groups_before = pre.exception_groups(campaign_id=campaign_id)
        grouped_before = sum(
            int(group["count"])
            for group in groups_before
            if group["exception_code"] == "system_block" and group["fingerprint"] == fingerprint
        )

        mass = MassOperationService(database)
        unauthorized_rejected = False
        try:
            mass.create_snapshot(
                campaign_id=campaign_id,
                actor=denied_operator,
                states=["hard_block"],
                exception_codes=["system_block"],
                maximum=items,
                snapshot_key=f"{key}-denied",
            )
        except MassOperationError as exc:
            unauthorized_rejected = exc.code == "brand_access_denied"

        snapshot_result = _timed(
            timings,
            "create_snapshot",
            mass.create_snapshot,
            campaign_id=campaign_id,
            actor=assigned_operator,
            states=["hard_block"],
            exception_codes=["system_block"],
            maximum=items,
            snapshot_key=f"{key}-authorized",
        )
        snapshot = snapshot_result["snapshot"]
        first_item_id = UUID(str(item_ids[0]))
        with database.connection() as conn:
            first_item = conn.execute(
                "SELECT updated_at,title,priority FROM football_brief.production_campaign_items WHERE id=%s",
                (first_item_id,),
            ).fetchone()
        stale_timestamp = first_item["updated_at"]
        edit = _timed(
            timings,
            "optimistic_inline_edit",
            mass.inline_edit,
            campaign_item_id=first_item_id,
            expected_updated_at=stale_timestamp,
            actor=assigned_operator,
            title=f"Updated mass operation item {key}",
            priority=75,
        )
        optimistic_edit_passed = bool(edit["ok"])
        stale_edit_rejected = False
        try:
            mass.inline_edit(
                campaign_item_id=first_item_id,
                expected_updated_at=stale_timestamp,
                actor=assigned_operator,
                priority=80,
            )
        except MassOperationError as exc:
            stale_edit_rejected = exc.code == "campaign_item_optimistic_lock_conflict"

        queued = _timed(
            timings,
            "enqueue_background_job",
            mass.enqueue_retry,
            snapshot_id=UUID(str(snapshot["id"])),
            actor=assigned_operator,
        )
        completed = _timed(
            timings,
            "execute_background_job",
            mass.execute_job,
            job_id=UUID(str(queued["job"]["id"])),
            actor=assigned_operator,
        )
        job = completed["job"]
        groups_after = pre.exception_groups(campaign_id=campaign_id)
        grouped_after = sum(
            int(group["count"])
            for group in groups_after
            if group["exception_code"] == "system_block" and group["fingerprint"] == fingerprint
        )
        with database.connection() as conn:
            result_rows = int(
                conn.execute(
                    """SELECT count(*)::int AS value
                       FROM football_brief.campaign_mass_operation_item_results WHERE job_id=%s""",
                    (job["id"],),
                ).fetchone()["value"]
            )
            succeeded_rows = int(
                conn.execute(
                    """SELECT count(*)::int AS value
                       FROM football_brief.campaign_mass_operation_item_results
                       WHERE job_id=%s AND outcome='succeeded'""",
                    (job["id"],),
                ).fetchone()["value"]
            )
            queued_runs = int(
                conn.execute(
                    """SELECT count(*)::int AS value
                       FROM football_brief.pre_generation_runs run
                       JOIN football_brief.production_campaign_items item ON item.id=run.campaign_item_id
                       WHERE item.campaign_version_id=%s AND run.status='queued'""",
                    (version_id,),
                ).fetchone()["value"]
            )

        passed = (
            int(snapshot["item_count"]) == items
            and int(job["succeeded_count"]) == items
            and int(job["skipped_count"]) == 0
            and int(job["failed_count"]) == 0
            and result_rows == items
            and succeeded_rows == items
            and queued_runs == items
            and grouped_before == items
            and grouped_after == 0
            and optimistic_edit_passed
            and stale_edit_rejected
            and unauthorized_rejected
        )
        counters = {
            "job_id": str(job["id"]),
            "snapshot_id": str(snapshot["id"]),
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "result_rows": result_rows,
            "succeeded_rows": succeeded_rows,
            "queued_runs": queued_runs,
        }
        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.mass_operations_acceptance_runs
                   SET status=%s,snapshot_items=%s,succeeded_items=%s,skipped_items=%s,
                       failed_items=%s,exact_result_rows=%s,grouped_exceptions_before=%s,
                       grouped_exceptions_after=%s,optimistic_edit_passed=%s,
                       stale_edit_rejected=%s,authorized_brand_action_passed=%s,
                       unauthorized_brand_action_rejected=%s,timings_ms=%s::jsonb,
                       counters=%s::jsonb,error=%s::jsonb,completed_at=now()
                   WHERE id=%s""",
                (
                    "passed" if passed else "failed",
                    snapshot["item_count"],
                    job["succeeded_count"],
                    job["skipped_count"],
                    job["failed_count"],
                    result_rows,
                    grouped_before,
                    grouped_after,
                    optimistic_edit_passed,
                    stale_edit_rejected,
                    True,
                    unauthorized_rejected,
                    _json(timings),
                    _json(counters),
                    _json({}) if passed else _json({"reason": "mass_operations_acceptance_mismatch"}),
                    acceptance_id,
                ),
            )
        if not passed:
            raise RuntimeError(f"mass operations acceptance failed: {counters}")
        return {
            "ok": True,
            "kind": "p130_mass_operations_acceptance",
            "acceptance_key": key,
            "items": items,
            "timings_ms": timings,
            "counters": counters,
        }
    except Exception as exc:
        if acceptance_id is not None:
            with database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.mass_operations_acceptance_runs
                       SET status='failed',error=%s::jsonb,timings_ms=%s::jsonb,completed_at=now()
                       WHERE id=%s AND status='running'""",
                    (_json({"type": type(exc).__name__, "message": str(exc)}), _json(timings), acceptance_id),
                )
        raise
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P130 mass operations acceptance")
    parser.add_argument("--items", type=int, default=1_000)
    parser.add_argument("--acceptance-key")
    args = parser.parse_args()
    print(_json(run_acceptance(items=args.items, acceptance_key=args.acceptance_key)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
