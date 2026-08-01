from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

from src.operator_api.access import AccessPermission, OperatorAccessService

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class MassOperationError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _snapshot_key() -> str:
    return datetime.now(timezone.utc).strftime("selection-%Y%m%dt%H%M%S%fz")


class MassOperationService:
    def __init__(self, database: "Database") -> None:
        self.database = database
        self.access = OperatorAccessService(database)

    def create_snapshot(
        self,
        *,
        campaign_id: UUID,
        actor: str,
        states: Iterable[str] = (),
        exception_codes: Iterable[str] = (),
        maximum: int = 20_000,
        snapshot_key: str | None = None,
    ) -> dict[str, Any]:
        if not 1 <= maximum <= 20_000:
            raise MassOperationError("snapshot_maximum_must_be_1_to_20000")
        normalized_states = sorted({str(value).strip() for value in states if str(value).strip()})
        normalized_exceptions = sorted(
            {str(value).strip() for value in exception_codes if str(value).strip()}
        )
        with self.database.transaction() as conn:
            campaign = self._campaign(conn, campaign_id)
            self._require_access(
                actor,
                AccessPermission.RUN_PRODUCTION,
                brand_id=str(campaign["brand_id"]),
            )
            conditions = ["version.campaign_id=%s"]
            values: list[Any] = [campaign_id]
            if normalized_states:
                conditions.append("item.state=ANY(%s::text[])")
                values.append(normalized_states)
            if normalized_exceptions:
                conditions.append(
                    "EXISTS (SELECT 1 FROM football_brief.pre_generation_exceptions exception "
                    "WHERE exception.campaign_item_id=item.id AND exception.status='open' "
                    "AND exception.exception_code=ANY(%s::text[]))"
                )
                values.append(normalized_exceptions)
            values.append(maximum + 1)
            rows = conn.execute(
                f"""SELECT item.id,item.ordinal,item.updated_at
                     FROM football_brief.production_campaign_items item
                     JOIN football_brief.production_campaign_versions version
                       ON version.id=item.campaign_version_id
                     WHERE {' AND '.join(conditions)}
                     ORDER BY item.ordinal,item.id LIMIT %s""",
                tuple(values),
            ).fetchall()
            if not rows:
                raise MassOperationError("snapshot_selection_empty")
            if len(rows) > maximum:
                raise MassOperationError(
                    "snapshot_selection_exceeds_maximum",
                    details={"maximum": maximum},
                )
            digest = _sha(
                [
                    {
                        "item_id": str(row["id"]),
                        "ordinal": int(row["ordinal"]),
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ]
            )
            snapshot = conn.execute(
                """INSERT INTO football_brief.campaign_selection_snapshots
                   (campaign_id,snapshot_key,status,filters,item_count,snapshot_sha256,created_by)
                   VALUES (%s,%s,'active',%s::jsonb,%s,%s,%s) RETURNING *""",
                (
                    campaign_id,
                    snapshot_key or _snapshot_key(),
                    _json({"states": normalized_states, "exception_codes": normalized_exceptions}),
                    len(rows),
                    digest,
                    actor,
                ),
            ).fetchone()
            conn.executemany(
                """INSERT INTO football_brief.campaign_selection_members
                   (snapshot_id,campaign_item_id,ordinal,item_updated_at)
                   VALUES (%s,%s,%s,%s)""",
                [
                    (snapshot["id"], row["id"], index, row["updated_at"])
                    for index, row in enumerate(rows, start=1)
                ],
            )
        return {"ok": True, "snapshot": dict(snapshot)}

    def enqueue_retry(self, *, snapshot_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            snapshot = conn.execute(
                """SELECT snapshot.*,campaign.brand_id
                   FROM football_brief.campaign_selection_snapshots snapshot
                   JOIN football_brief.production_campaigns campaign ON campaign.id=snapshot.campaign_id
                   WHERE snapshot.id=%s FOR UPDATE OF snapshot""",
                (snapshot_id,),
            ).fetchone()
            if snapshot is None:
                raise MassOperationError("snapshot_not_found")
            self._require_access(actor, AccessPermission.RUN_PRODUCTION, brand_id=str(snapshot["brand_id"]))
            if snapshot["status"] != "active":
                raise MassOperationError("snapshot_not_active")
            job = conn.execute(
                """INSERT INTO football_brief.campaign_mass_operation_jobs
                   (campaign_id,snapshot_id,action_type,status,requested_count,requested_by)
                   VALUES (%s,%s,'retry','queued',%s,%s) RETURNING *""",
                (snapshot["campaign_id"], snapshot_id, snapshot["item_count"], actor),
            ).fetchone()
        return {"ok": True, "job": dict(job)}

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
                   LEFT JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                   WHERE member.snapshot_id=%s
                   ORDER BY member.ordinal
                   FOR UPDATE OF item,run""",
                (job["snapshot_id"],),
            ).fetchall()
            eligible = [
                row
                for row in rows
                if row["run_id"] is not None
                and str(row["run_status"]) in {"human_exception", "hard_block", "failed", "waiting"}
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
            result_values = []
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

    def inline_edit(
        self,
        *,
        campaign_item_id: UUID,
        expected_updated_at: datetime,
        actor: str,
        title: str | None = None,
        priority: int | None = None,
    ) -> dict[str, Any]:
        if title is None and priority is None:
            raise MassOperationError("inline_edit_requires_change")
        if title is not None and not 3 <= len(title.strip()) <= 240:
            raise MassOperationError("invalid_inline_title")
        if priority is not None and not -1000 <= priority <= 1000:
            raise MassOperationError("invalid_inline_priority")
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT item.*,campaign.brand_id
                   FROM football_brief.production_campaign_items item
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   JOIN football_brief.production_campaigns campaign ON campaign.id=version.campaign_id
                   WHERE item.id=%s FOR UPDATE OF item""",
                (campaign_item_id,),
            ).fetchone()
            if row is None:
                raise MassOperationError("campaign_item_not_found")
            self._require_access(actor, AccessPermission.EDIT_CONTENT, brand_id=str(row["brand_id"]))
            if row["updated_at"] != expected_updated_at:
                raise MassOperationError("campaign_item_optimistic_lock_conflict")
            before = {"title": row["title"], "priority": row["priority"], "updated_at": row["updated_at"]}
            updated = conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET title=COALESCE(%s,title),priority=COALESCE(%s,priority),updated_at=clock_timestamp()
                   WHERE id=%s AND updated_at=%s RETURNING *""",
                (title.strip() if title is not None else None, priority, campaign_item_id, expected_updated_at),
            ).fetchone()
            if updated is None:
                raise MassOperationError("campaign_item_optimistic_lock_conflict")
            after = {"title": updated["title"], "priority": updated["priority"], "updated_at": updated["updated_at"]}
            event = conn.execute(
                """INSERT INTO football_brief.campaign_inline_edit_events
                   (campaign_item_id,expected_updated_at,before_state,after_state,edited_by)
                   VALUES (%s,%s,%s::jsonb,%s::jsonb,%s) RETURNING *""",
                (campaign_item_id, expected_updated_at, _json(before), _json(after), actor),
            ).fetchone()
        return {"ok": True, "item": dict(updated), "event": dict(event)}

    def _require_access(self, actor: str, permission: AccessPermission, *, brand_id: str) -> None:
        identity = self.access.identity(actor, key_name="mass-operation")
        if identity is None or not identity.active:
            raise MassOperationError("operator_inactive_or_missing")
        if not identity.permits(permission):
            raise MassOperationError("permission_denied")
        if not identity.can_access_brand(brand_id):
            raise MassOperationError("brand_access_denied")

    @staticmethod
    def _campaign(conn: Any, campaign_id: UUID) -> Any:
        row = conn.execute(
            "SELECT id,brand_id,status FROM football_brief.production_campaigns WHERE id=%s",
            (campaign_id,),
        ).fetchone()
        if row is None:
            raise MassOperationError("campaign_not_found")
        return row


__all__ = ["MassOperationError", "MassOperationService"]
