from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

from src.application.pre_generation.service import PreGenerationError, PreGenerationService


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class ValidatedPreGenerationService(PreGenerationService):
    def set_campaign_status(
        self,
        *,
        campaign_id: UUID,
        status: Literal["active", "paused"],
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            row = conn.execute(
                """SELECT * FROM football_brief.production_campaigns
                   WHERE id=%s FOR UPDATE""",
                (campaign_id,),
            ).fetchone()
            if row is None:
                raise PreGenerationError("campaign_not_found")
            current = str(row["status"])
            if status == "paused" and current not in {"active", "paused"}:
                raise PreGenerationError("only_active_campaign_can_be_paused")
            if status == "active" and current not in {"paused", "active"}:
                raise PreGenerationError("only_paused_campaign_can_be_resumed")
            action_type = "pause" if status == "paused" else "resume"
            action = conn.execute(
                """INSERT INTO football_brief.production_campaign_actions
                   (campaign_id,action_type,status,selection,requested_count,requested_by,
                    started_at,completed_at,result)
                   VALUES (%s,%s,'completed','{}'::jsonb,0,%s,now(),now(),%s::jsonb)
                   RETURNING *""",
                (
                    campaign_id,
                    action_type,
                    actor,
                    _json({"from_status": current, "to_status": status}),
                ),
            ).fetchone()
            updated = conn.execute(
                """UPDATE football_brief.production_campaigns
                   SET status=%s,updated_at=now() WHERE id=%s RETURNING *""",
                (status, campaign_id),
            ).fetchone()
        return {
            "ok": True,
            "kind": "pre_generation_campaign_status",
            "campaign": dict(updated),
            "action_id": str(action["id"]),
        }

    def retry_items(self, *, campaign_id: UUID, item_ids: list[UUID], actor: str) -> dict[str, Any]:
        if not item_ids or len(item_ids) > 1000:
            raise PreGenerationError("retry_selection_must_contain_1_to_1000_items")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            action = conn.execute(
                """INSERT INTO football_brief.production_campaign_actions
                   (campaign_id,action_type,status,selection,requested_count,requested_by,started_at)
                   VALUES (%s,'retry','running',%s::jsonb,%s,%s,now()) RETURNING *""",
                (campaign_id, _json({"item_ids": [str(value) for value in item_ids]}), len(item_ids), actor),
            ).fetchone()
            rows = conn.execute(
                """UPDATE football_brief.pre_generation_runs run
                   SET status='queued',lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,
                       next_attempt_at=now(),last_error_code=NULL,last_error_detail='{}'::jsonb,
                       updated_at=now()
                   FROM football_brief.production_campaign_items item
                   JOIN football_brief.production_campaign_versions version
                     ON version.id=item.campaign_version_id
                   WHERE run.campaign_item_id=item.id AND version.campaign_id=%s
                     AND item.id=ANY(%s::uuid[])
                     AND run.status IN ('human_exception','hard_block','failed','waiting')
                   RETURNING run.id AS run_id,item.id AS item_id""",
                (campaign_id, item_ids),
            ).fetchall()
            retried_item_ids = [row["item_id"] for row in rows]
            if retried_item_ids:
                conn.execute(
                    """UPDATE football_brief.production_campaign_items
                       SET state='auto_progressing',disposition=NULL,updated_at=now()
                       WHERE id=ANY(%s::uuid[])""",
                    (retried_item_ids,),
                )
                conn.execute(
                    """UPDATE football_brief.pre_generation_exceptions
                       SET status='superseded',resolved_at=now(),resolved_by=%s,
                           resolution=jsonb_build_object('action','retry')
                       WHERE campaign_item_id=ANY(%s::uuid[]) AND status='open'""",
                    (actor, retried_item_ids),
                )
            failed_count = len(item_ids) - len(rows)
            conn.execute(
                """UPDATE football_brief.production_campaign_actions
                   SET status=%s,succeeded_count=%s,failed_count=%s,completed_at=now(),
                       result=%s::jsonb WHERE id=%s""",
                (
                    "completed" if failed_count == 0 else "partial",
                    len(rows),
                    failed_count,
                    _json(
                        {
                            "retried_run_ids": [str(row["run_id"]) for row in rows],
                            "retried_item_ids": [str(row["item_id"]) for row in rows],
                        }
                    ),
                    action["id"],
                ),
            )
        return {
            "ok": True,
            "kind": "pre_generation_retry",
            "requested": len(item_ids),
            "retried": len(rows),
            "action_id": str(action["id"]),
        }

    def exception_groups(self, *, campaign_id: UUID) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT exception.category,exception.exception_code,exception.severity,
                          exception.rule_version,exception.fingerprint,
                          count(*)::int AS count,min(exception.created_at) AS oldest_at,
                          max(exception.created_at) AS newest_at,
                          array_agg(exception.campaign_item_id ORDER BY item.ordinal)[:20]
                            AS sample_item_ids
                   FROM football_brief.pre_generation_exceptions exception
                   JOIN football_brief.production_campaign_items item
                     ON item.id=exception.campaign_item_id
                   JOIN football_brief.production_campaign_versions version
                     ON version.id=item.campaign_version_id
                   WHERE version.campaign_id=%s AND exception.status='open'
                   GROUP BY exception.category,exception.exception_code,exception.severity,
                            exception.rule_version,exception.fingerprint
                   ORDER BY CASE exception.severity WHEN 'hard_block' THEN 0 ELSE 1 END,
                            count(*) DESC,exception.exception_code""",
                (campaign_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_exception_group(
        self,
        *,
        campaign_id: UUID,
        exception_code: str,
        rule_version: str,
        fingerprint: str,
        action: Literal["retry", "waive"],
        rationale: str,
        actor: str,
    ) -> dict[str, Any]:
        if len(rationale.strip()) < 5:
            raise PreGenerationError("exception_resolution_rationale_required")
        with self.database.transaction() as conn:
            self._require_operator(conn, actor)
            exceptions = conn.execute(
                """SELECT exception.*,run.status AS run_status,item.state AS item_state
                   FROM football_brief.pre_generation_exceptions exception
                   JOIN football_brief.pre_generation_runs run ON run.id=exception.run_id
                   JOIN football_brief.production_campaign_items item ON item.id=exception.campaign_item_id
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   WHERE version.campaign_id=%s AND exception.status='open'
                     AND exception.exception_code=%s AND exception.rule_version=%s
                     AND exception.fingerprint=%s
                   FOR UPDATE OF exception,run,item""",
                (campaign_id, exception_code, rule_version, fingerprint),
            ).fetchall()
            if not exceptions:
                raise PreGenerationError("exception_group_not_found")
            if action == "waive" and any(str(row["severity"]) == "hard_block" for row in exceptions):
                raise PreGenerationError("hard_block_cannot_be_waived")
            item_ids = [row["campaign_item_id"] for row in exceptions]
            run_ids = [row["run_id"] for row in exceptions]
            conn.execute(
                """UPDATE football_brief.pre_generation_exceptions
                   SET status=%s,resolved_at=now(),resolved_by=%s,
                       resolution=%s::jsonb
                   WHERE id=ANY(%s::uuid[])""",
                (
                    "waived" if action == "waive" else "superseded",
                    actor,
                    _json({"action": action, "rationale": rationale}),
                    [row["id"] for row in exceptions],
                ),
            )
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET status='queued',lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,
                       next_attempt_at=now(),last_error_code=NULL,last_error_detail='{}'::jsonb,
                       updated_at=now(),metadata=metadata || %s::jsonb
                   WHERE id=ANY(%s::uuid[])""",
                (
                    _json({"exception_resolution": {"action": action, "rationale": rationale, "actor": actor}}),
                    run_ids,
                ),
            )
            conn.execute(
                """UPDATE football_brief.production_campaign_items
                   SET state='auto_progressing',disposition=NULL,updated_at=now()
                   WHERE id=ANY(%s::uuid[])""",
                (item_ids,),
            )
            action_row = conn.execute(
                """INSERT INTO football_brief.production_campaign_actions
                   (campaign_id,action_type,status,selection,requested_count,succeeded_count,
                    failed_count,result,requested_by,started_at,completed_at)
                   VALUES (%s,'resolve_exception','completed',%s::jsonb,%s,%s,0,%s::jsonb,
                           %s,now(),now()) RETURNING *""",
                (
                    campaign_id,
                    _json(
                        {
                            "exception_code": exception_code,
                            "rule_version": rule_version,
                            "fingerprint": fingerprint,
                        }
                    ),
                    len(exceptions),
                    len(exceptions),
                    _json({"action": action, "rationale": rationale, "item_ids": [str(value) for value in item_ids]}),
                    actor,
                ),
            ).fetchone()
        return {
            "ok": True,
            "kind": "pre_generation_exception_group_resolved",
            "count": len(exceptions),
            "action": action,
            "action_id": str(action_row["id"]),
        }

    def package_for_item(self, *, campaign_id: UUID, item_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT package.*,item.item_key,item.title,item.state,item.disposition
                   FROM football_brief.pre_generation_packages package
                   JOIN football_brief.production_campaign_items item ON item.id=package.campaign_item_id
                   JOIN football_brief.production_campaign_versions version ON version.id=item.campaign_version_id
                   WHERE version.campaign_id=%s AND item.id=%s AND package.status='ready'""",
                (campaign_id, item_id),
            ).fetchone()
        if row is None:
            raise PreGenerationError("ready_pre_generation_package_not_found")
        return {"ok": True, "kind": "pre_generation_package", "package": dict(row)}


__all__ = ["ValidatedPreGenerationService"]
