from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.mass_operations.service import MassOperationError, MassOperationService, _json
from src.operator_api.access import AccessPermission


class ValidatedMassOperationService(MassOperationService):
    def execute_job(self, *, job_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            job = conn.execute(
                """SELECT job.*,campaign.brand_id,snapshot.status AS snapshot_status
                   FROM football_brief.campaign_mass_operation_jobs job
                   JOIN football_brief.production_campaigns campaign ON campaign.id=job.campaign_id
                   JOIN football_brief.campaign_selection_snapshots snapshot ON snapshot.id=job.snapshot_id
                   WHERE job.id=%s FOR UPDATE OF job""",
                (job_id,),
            ).fetchone()
            if job is None:
                raise MassOperationError("mass_operation_job_not_found")
            self._require_access(actor, AccessPermission.RUN_PRODUCTION, brand_id=str(job["brand_id"]))
            if job["status"] != "queued":
                raise MassOperationError("mass_operation_job_not_queued")
            conn.execute(
                """UPDATE football_brief.campaign_mass_operation_jobs
                   SET status='running',started_at=now() WHERE id=%s""",
                (job_id,),
            )
            rows = conn.execute(
                """SELECT member.campaign_item_id,item.state,item.disposition,item.updated_at,
                          run.id AS run_id,run.status AS run_status,run.current_stage,
                          run.last_error_code
                   FROM football_brief.campaign_selection_members member
                   JOIN football_brief.production_campaign_items item ON item.id=member.campaign_item_id
                   JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                   WHERE member.snapshot_id=%s
                   ORDER BY member.ordinal
                   FOR UPDATE OF item,run""",
                (job["snapshot_id"],),
            ).fetchall()
            eligible = [
                row
                for row in rows
                if str(row["run_status"]) in {"human_exception", "hard_block", "failed", "waiting"}
            ]
            eligible_item_ids = [row["campaign_item_id"] for row in eligible]
            eligible_run_ids = [row["run_id"] for row in eligible]
            if eligible_run_ids:
                conn.execute(
                    """UPDATE football_brief.pre_generation_runs
                       SET status='queued',lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,
                           next_attempt_at=now(),last_error_code=NULL,last_error_detail='{}'::jsonb,
                           updated_at=now()
                       WHERE id=ANY(%s::uuid[])""",
                    (eligible_run_ids,),
                )
                conn.execute(
                    """UPDATE football_brief.production_campaign_items
                       SET state='auto_progressing',disposition=NULL,updated_at=now()
                       WHERE id=ANY(%s::uuid[])""",
                    (eligible_item_ids,),
                )
                conn.execute(
                    """UPDATE football_brief.pre_generation_exceptions
                       SET status='superseded',resolved_at=now(),resolved_by=%s,
                           resolution=jsonb_build_object('action','snapshot_retry','job_id',%s::text)
                       WHERE campaign_item_id=ANY(%s::uuid[]) AND status='open'""",
                    (actor, job_id, eligible_item_ids),
                )
            eligible_ids = {row["campaign_item_id"] for row in eligible}
            result_values: list[tuple[Any, ...]] = []
            for row in rows:
                succeeded = row["campaign_item_id"] in eligible_ids
                before = {
                    "item_state": row["state"],
                    "disposition": row["disposition"],
                    "run_status": row["run_status"],
                    "current_stage": row["current_stage"],
                    "last_error_code": row["last_error_code"],
                }
                after = (
                    {
                        "item_state": "auto_progressing",
                        "disposition": None,
                        "run_status": "queued",
                        "current_stage": row["current_stage"],
                        "last_error_code": None,
                    }
                    if succeeded
                    else before
                )
                result_values.append(
                    (
                        job_id,
                        row["campaign_item_id"],
                        "succeeded" if succeeded else "skipped",
                        _json(before),
                        _json(after),
                        None,
                    )
                )
            conn.executemany(
                """INSERT INTO football_brief.campaign_mass_operation_item_results
                   (job_id,campaign_item_id,outcome,before_state,after_state,error_code)
                   VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s)""",
                result_values,
            )
            succeeded_count = len(eligible)
            skipped_count = len(rows) - succeeded_count
            status = "completed" if skipped_count == 0 else "partial"
            action = conn.execute(
                """INSERT INTO football_brief.production_campaign_actions
                   (campaign_id,action_type,status,selection,requested_count,succeeded_count,
                    failed_count,result,requested_by,started_at,completed_at)
                   VALUES (%s,'retry',%s,%s::jsonb,%s,%s,%s,%s::jsonb,%s,now(),now())
                   RETURNING id""",
                (
                    job["campaign_id"],
                    status,
                    _json({"snapshot_id": str(job["snapshot_id"]), "job_id": str(job_id)}),
                    len(rows),
                    succeeded_count,
                    skipped_count,
                    _json({"skipped_count": skipped_count, "exact_result_rows": len(rows)}),
                    actor,
                ),
            ).fetchone()
            completed = conn.execute(
                """UPDATE football_brief.campaign_mass_operation_jobs
                   SET status=%s,succeeded_count=%s,skipped_count=%s,failed_count=0,
                       completed_at=now(),result=%s::jsonb
                   WHERE id=%s RETURNING *""",
                (
                    status,
                    succeeded_count,
                    skipped_count,
                    _json({"production_campaign_action_id": str(action["id"]), "result_rows": len(rows)}),
                    job_id,
                ),
            ).fetchone()
            conn.execute(
                """UPDATE football_brief.campaign_selection_snapshots
                   SET status='consumed',consumed_at=now() WHERE id=%s""",
                (job["snapshot_id"],),
            )
        return {"ok": True, "job": dict(completed)}


__all__ = ["ValidatedMassOperationService"]
