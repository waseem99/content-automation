from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.p4_dashboard import P4DashboardContracts
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class P4AuditError(RuntimeError):
    pass


class P4AuditReportService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.dashboard = P4DashboardContracts(database)

    def report(self, *, workflow_run_id: UUID) -> dict[str, Any]:
        with unit_of_work(self.database) as uow:
            workflow = uow.conn.execute(
                """
                SELECT wr.*, ci.slug AS content_slug, ci.working_title AS content_title
                FROM football_brief.workflow_runs wr
                JOIN football_brief.content_items ci ON ci.id = wr.content_item_id
                WHERE wr.id = %s
                """,
                (workflow_run_id,),
            ).fetchone()
            if workflow is None:
                return {"ok": False, "kind": "audit_report", "error": "workflow was not found"}
            events = uow.conn.execute(
                """
                SELECT id, workflow_run_id, stage_execution_id, event_type, from_status,
                       to_status, actor, reason, payload, created_at
                FROM football_brief.workflow_events
                WHERE workflow_run_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (workflow_run_id,),
            ).fetchall()
            stages = uow.conn.execute(
                """
                SELECT id, workflow_run_id, stage_name, stage_version, status, attempt,
                       input_hash, output_hash, actual_cost_usd, failure_reason,
                       operator, created_at, started_at, completed_at
                FROM football_brief.stage_executions
                WHERE workflow_run_id = %s
                ORDER BY created_at ASC, stage_name ASC, attempt ASC
                """,
                (workflow_run_id,),
            ).fetchall()
            reviews = _review_rows(uow.conn, workflow_run_id)
            packages = uow.conn.execute(
                """
                SELECT p.id, p.workflow_run_id, p.step_plan_id, p.stage_execution_id,
                       p.package_hash, p.option_ids, p.metadata, p.created_by, p.created_at,
                       COALESCE(r.status, 'missing') AS review_status,
                       r.reviewed_by, r.rationale, r.reviewed_at
                FROM football_brief.p3_packages p
                LEFT JOIN football_brief.p3_package_reviews r
                  ON r.workflow_run_id = p.workflow_run_id AND r.package_id = p.id
                WHERE p.workflow_run_id = %s
                ORDER BY p.created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
            manifests = uow.conn.execute(
                """
                SELECT id, workflow_run_id, package_id, step_plan_id, stage_execution_id,
                       manifest_hash, approval_metadata, package_metadata, created_by, created_at
                FROM football_brief.p3_delivery_manifests
                WHERE workflow_run_id = %s
                ORDER BY created_at DESC
                """,
                (workflow_run_id,),
            ).fetchall()
        queue = self.dashboard.queue_cards(workflow_run_id=workflow_run_id)
        queue_cards = queue.get("cards", []) if queue.get("ok") else []
        blocked_reason = _blocked_reason(workflow, queue_cards, reviews)
        payload = {
            "ok": True,
            "kind": "audit_report",
            "workflow_run_id": str(workflow_run_id),
            "workflow": {
                "id": workflow["id"],
                "status": workflow["status"],
                "current_stage": workflow["current_stage"],
                "workflow_name": workflow["workflow_name"],
                "workflow_version": workflow["workflow_version"],
                "content_item_id": workflow["content_item_id"],
                "content_slug": workflow["content_slug"],
                "content_title": workflow["content_title"],
                "started_at": workflow["started_at"],
                "completed_at": workflow["completed_at"],
                "failure_reason": workflow["failure_reason"],
                "actual_cost_usd": workflow["actual_cost_usd"],
            },
            "status": {
                "is_blocked": bool(blocked_reason),
                "blocked_reason": blocked_reason,
                "queue_count": len(queue_cards),
                "event_count": len(events),
                "stage_count": len(stages),
                "review_count": len(reviews),
                "package_count": len(packages),
                "manifest_count": len(manifests),
            },
            "timeline": [_event_payload(row) for row in events],
            "stages": [_row_payload(row) for row in stages],
            "reviews": reviews,
            "queue": queue_cards,
            "packages": [_row_payload(row) for row in packages],
            "manifests": [_row_payload(row) for row in manifests],
        }
        return _json_ready(payload)


def _review_rows(conn, workflow_run_id: UUID) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in conn.execute(
        """
        SELECT 'packet_review' AS review_type, id, workflow_run_id, packet_id AS resource_id,
               status, reviewed_by, rationale, created_at, reviewed_at
        FROM football_brief.review_prerequisites
        WHERE workflow_run_id = %s
        """,
        (workflow_run_id,),
    ).fetchall():
        rows.append(_row_payload(row))
    for row in conn.execute(
        """
        SELECT 'source_output_review' AS review_type, id, workflow_run_id, source_output_id AS resource_id,
               status, reviewed_by, rationale, created_at, reviewed_at
        FROM football_brief.source_output_reviews
        WHERE workflow_run_id = %s
        """,
        (workflow_run_id,),
    ).fetchall():
        rows.append(_row_payload(row))
    for row in conn.execute(
        """
        SELECT 'p3_option_review' AS review_type, id, workflow_run_id, option_id AS resource_id,
               status, reviewed_by, rationale, created_at, reviewed_at
        FROM football_brief.p3_option_reviews
        WHERE workflow_run_id = %s
        """,
        (workflow_run_id,),
    ).fetchall():
        rows.append(_row_payload(row))
    for row in conn.execute(
        """
        SELECT 'p3_plan_review' AS review_type, id, workflow_run_id, step_plan_id AS resource_id,
               status, reviewed_by, rationale, created_at, reviewed_at
        FROM football_brief.p3_plan_reviews
        WHERE workflow_run_id = %s
        """,
        (workflow_run_id,),
    ).fetchall():
        rows.append(_row_payload(row))
    for row in conn.execute(
        """
        SELECT 'package_review' AS review_type, id, workflow_run_id, package_id AS resource_id,
               status, reviewed_by, rationale, created_at, reviewed_at
        FROM football_brief.p3_package_reviews
        WHERE workflow_run_id = %s
        """,
        (workflow_run_id,),
    ).fetchall():
        rows.append(_row_payload(row))
    return sorted(rows, key=lambda item: item.get("created_at") or "")


def _blocked_reason(workflow: dict[str, Any], queue_cards: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> str | None:
    if workflow.get("failure_reason"):
        return str(workflow["failure_reason"])
    if workflow.get("status") == "failed":
        return "workflow failed"
    if queue_cards:
        first = queue_cards[0]
        return f"{first.get('item_type')}:{first.get('status')}"
    for review in reviews:
        if review.get("status") not in {"approved"}:
            return f"{review.get('review_type')}:{review.get('status')}"
    return None


def _event_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "event_type": row["event_type"],
        "stage_execution_id": row["stage_execution_id"],
        "from_status": row["from_status"],
        "to_status": row["to_status"],
        "actor": row["actor"],
        "reason": row["reason"],
        "payload": row["payload"],
        "created_at": row["created_at"],
    }


def _row_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(row).items()}


def _json_ready(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value
