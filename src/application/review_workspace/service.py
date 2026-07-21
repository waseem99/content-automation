from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

from src.application.review_workspace.models import (
    CompareTarget,
    InboxFilters,
    ReviewCommentRequest,
    ReviewTarget,
    RevisionTaskStatus,
    TaskMutationRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class ReviewWorkspaceError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


TARGET_COLUMN = {
    ReviewTarget.WORKFLOW_VERSION: "target_workflow_version_id",
    ReviewTarget.SCRIPT_VERSION: "target_script_version_id",
    ReviewTarget.SCRIPT_SECTION: "target_script_section_id",
    ReviewTarget.AUDIO_MIX_VERSION: "target_audio_mix_version_id",
    ReviewTarget.AUDIO_PARAGRAPH: "target_audio_paragraph_id",
    ReviewTarget.VISUAL_SHOT_VERSION: "target_visual_shot_version_id",
    ReviewTarget.VISUAL_CANDIDATE: "target_visual_candidate_id",
}


class ReviewWorkspaceService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def inbox(
        self,
        *,
        filters: InboxFilters,
        allowed_brand_ids: Iterable[UUID] | None,
    ) -> list[dict[str, Any]]:
        conditions = ["true"]
        values: list[Any] = []
        scoped = [UUID(str(value)) for value in allowed_brand_ids] if allowed_brand_ids is not None else None
        requested = [UUID(str(value)) for value in filters.brand_ids]
        if scoped is not None:
            selected = sorted(set(scoped).intersection(requested or scoped), key=str)
            if not selected:
                return []
            conditions.append("brand_id=ANY(%s::uuid[])")
            values.append(selected)
        elif requested:
            conditions.append("brand_id=ANY(%s::uuid[])")
            values.append(requested)
        if filters.stages:
            conditions.append("stage=ANY(%s::text[])")
            values.append(list(filters.stages))
        if filters.assignee_operator_id:
            conditions.append("assignee_operator_id=%s")
            values.append(filters.assignee_operator_id)
        if filters.due_from:
            conditions.append("due_at>=%s")
            values.append(filters.due_from)
        if filters.due_to:
            conditions.append("due_at<=%s")
            values.append(filters.due_to)
        if filters.statuses:
            conditions.append("status=ANY(%s::text[])")
            values.append(list(filters.statuses))
        if filters.blocker is not None:
            conditions.append("blocker=%s")
            values.append(filters.blocker)
        if filters.overdue is not None:
            conditions.append("overdue=%s")
            values.append(filters.overdue)
        if filters.item_types:
            conditions.append("inbox_item_type=ANY(%s::text[])")
            values.append(list(filters.item_types))
        values.append(filters.limit)
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT * FROM football_brief.creator_review_inbox
                    WHERE {' AND '.join(conditions)}
                    ORDER BY blocker DESC, overdue DESC, due_at NULLS LAST,
                             created_at, inbox_item_id
                    LIMIT %s""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def workspace(self, *, content_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            content = conn.execute(
                """SELECT pc.*,mp.brand_id,b.slug AS brand_slug,b.display_name AS brand_name
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
            if not content:
                raise ReviewWorkspaceError("content_not_found")
            workflow = conn.execute(
                """SELECT pw.*,pwv.version AS current_version,
                          pwv.status AS current_version_status,pwv.parent_version_id,
                          pwv.snapshot AS current_snapshot
                   FROM football_brief.production_workflows pw
                   JOIN football_brief.production_workflow_versions pwv
                     ON pwv.id=pw.current_version_id
                   WHERE pw.portfolio_content_id=%s""",
                (content_id,),
            ).fetchone()
            assignments = conn.execute(
                """SELECT pwa.*,ou.display_name AS assignee_name
                   FROM football_brief.production_workflow_assignments pwa
                   JOIN football_brief.operator_users ou
                     ON ou.operator_id=pwa.assignee_operator_id
                   JOIN football_brief.production_workflows pw ON pw.id=pwa.workflow_id
                   WHERE pw.portfolio_content_id=%s
                   ORDER BY pwa.active DESC,pwa.created_at DESC""",
                (content_id,),
            ).fetchall()
            scripts = conn.execute(
                """SELECT sv.*,sd.id AS script_document_id,
                          sd.current_version_id=sv.id AS is_current
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.script_document_id=sd.id
                   WHERE sd.portfolio_content_id=%s
                   ORDER BY sv.version DESC""",
                (content_id,),
            ).fetchall()
            audio = conn.execute(
                """SELECT ap.*,amv.version AS current_mix_version,
                          amv.status AS current_mix_status,amv.qc_status AS current_mix_qc,
                          amv.alignment_source,amv.duration_seconds
                   FROM football_brief.audio_productions ap
                   LEFT JOIN football_brief.audio_mix_versions amv
                     ON amv.id=ap.current_mix_version_id
                   WHERE ap.portfolio_content_id=%s
                   ORDER BY ap.created_at DESC""",
                (content_id,),
            ).fetchall()
            visuals = conn.execute(
                """SELECT vp.*,count(vs.id) AS shot_count,
                          count(vs.id) FILTER (WHERE vs.status='approved') AS approved_shot_count
                   FROM football_brief.visual_projects vp
                   LEFT JOIN football_brief.visual_shots vs ON vs.visual_project_id=vp.id
                   WHERE vp.portfolio_content_id=%s
                   GROUP BY vp.id
                   ORDER BY vp.created_at DESC""",
                (content_id,),
            ).fetchall()
            comments = conn.execute(
                """SELECT crc.*,ou.display_name AS author_name
                   FROM football_brief.creator_review_comments crc
                   JOIN football_brief.operator_users ou
                     ON ou.operator_id=crc.author_operator_id
                   WHERE crc.portfolio_content_id=%s
                   ORDER BY crc.created_at,crc.id""",
                (content_id,),
            ).fetchall()
            tasks = conn.execute(
                """SELECT crt.*,ou.display_name AS assignee_name
                   FROM football_brief.creator_revision_tasks crt
                   JOIN football_brief.operator_users ou
                     ON ou.operator_id=crt.assignee_operator_id
                   WHERE crt.portfolio_content_id=%s
                   ORDER BY CASE crt.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
                            crt.blocker DESC,crt.due_at NULLS LAST,crt.created_at""",
                (content_id,),
            ).fetchall()
        return {
            "ok": True,
            "content": dict(content),
            "workflow": dict(workflow) if workflow else None,
            "assignments": [dict(row) for row in assignments],
            "script_versions": [dict(row) for row in scripts],
            "audio_productions": [dict(row) for row in audio],
            "visual_projects": [dict(row) for row in visuals],
            "comments": [dict(row) for row in comments],
            "revision_tasks": [dict(row) for row in tasks],
        }

    def create_comment(
        self,
        *,
        request: ReviewCommentRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            target = self._resolve_target(conn, request.target_type, request.target_id)
            workflow = conn.execute(
                """SELECT * FROM football_brief.production_workflows
                   WHERE portfolio_content_id=%s FOR UPDATE""",
                (target["portfolio_content_id"],),
            ).fetchone()
            if not workflow:
                raise ReviewWorkspaceError("production_workflow_not_found")
            target_values = {column: None for column in TARGET_COLUMN.values()}
            target_values[TARGET_COLUMN[request.target_type]] = request.target_id
            comment = conn.execute(
                """INSERT INTO football_brief.creator_review_comments
                   (portfolio_content_id,production_workflow_id,workflow_version_id,stage,
                    target_type,target_workflow_version_id,target_script_version_id,
                    target_script_section_id,target_audio_mix_version_id,target_audio_paragraph_id,
                    target_visual_shot_version_id,target_visual_candidate_id,
                    timeline_start_ms,timeline_end_ms,comment_type,body,blocking,
                    author_operator_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (
                    target["portfolio_content_id"],workflow["id"],workflow["current_version_id"],
                    workflow["current_stage"],request.target_type.value,
                    target_values["target_workflow_version_id"],
                    target_values["target_script_version_id"],
                    target_values["target_script_section_id"],
                    target_values["target_audio_mix_version_id"],
                    target_values["target_audio_paragraph_id"],
                    target_values["target_visual_shot_version_id"],
                    target_values["target_visual_candidate_id"],
                    request.timeline_start_ms,request.timeline_end_ms,
                    request.comment_type.value,request.body,request.blocking,actor,
                ),
            ).fetchone()
            task = None
            if request.revision_task is not None:
                task_request = request.revision_task
                task = conn.execute(
                    """INSERT INTO football_brief.creator_revision_tasks
                       (source_comment_id,portfolio_content_id,production_workflow_id,
                        workflow_version_id,stage,target_type,target_workflow_version_id,
                        target_script_version_id,target_script_section_id,target_audio_mix_version_id,
                        target_audio_paragraph_id,target_visual_shot_version_id,
                        target_visual_candidate_id,task_type,title,instructions,
                        assignee_operator_id,assigned_by_operator_id,updated_by_operator_id,
                        due_at,priority,status,blocker,lock_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'open',%s,1)
                       RETURNING *""",
                    (
                        comment["id"],target["portfolio_content_id"],workflow["id"],
                        workflow["current_version_id"],workflow["current_stage"],
                        request.target_type.value,
                        target_values["target_workflow_version_id"],
                        target_values["target_script_version_id"],
                        target_values["target_script_section_id"],
                        target_values["target_audio_mix_version_id"],
                        target_values["target_audio_paragraph_id"],
                        target_values["target_visual_shot_version_id"],
                        target_values["target_visual_candidate_id"],
                        task_request.task_type.value,task_request.title,
                        task_request.instructions,task_request.assignee_operator_id,
                        actor,actor,task_request.due_at,task_request.priority.value,
                        task_request.blocker,
                    ),
                ).fetchone()
        return {
            "ok": True,
            "comment": dict(comment),
            "revision_task": dict(task) if task else None,
        }

    def resolve_comment(self, *, comment_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            row = conn.execute(
                """UPDATE football_brief.creator_review_comments
                   SET resolved_by_operator_id=%s,resolved_at=now()
                   WHERE id=%s AND resolved_at IS NULL RETURNING *""",
                (actor,comment_id),
            ).fetchone()
            if not row:
                raise ReviewWorkspaceError("review_comment_not_found_or_resolved")
        return {"ok": True, "comment": dict(row)}

    def mutate_task(
        self,
        *,
        task_id: UUID,
        request: TaskMutationRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            task = conn.execute(
                "SELECT * FROM football_brief.creator_revision_tasks WHERE id=%s FOR UPDATE",
                (task_id,),
            ).fetchone()
            if not task:
                raise ReviewWorkspaceError("revision_task_not_found")
            if int(task["lock_version"]) != request.expected_lock_version:
                raise ReviewWorkspaceError(
                    "revision_task_conflict",
                    details={"expected": request.expected_lock_version, "current": int(task["lock_version"])},
                )
            field: str
            value: Any
            timestamp_sql = ""
            if request.status is not None:
                field = "status"
                value = request.status.value
                if request.status == RevisionTaskStatus.IN_PROGRESS:
                    timestamp_sql = ",started_at=COALESCE(started_at,now())"
                elif request.status == RevisionTaskStatus.COMPLETED:
                    timestamp_sql = ",completed_at=now()"
                elif request.status == RevisionTaskStatus.CANCELLED:
                    timestamp_sql = ",cancelled_at=now()"
            elif request.assignee_operator_id is not None:
                field = "assignee_operator_id"
                value = request.assignee_operator_id
            elif request.due_at is not None or request.clear_due_at:
                field = "due_at"
                value = request.due_at
            elif request.priority is not None:
                field = "priority"
                value = request.priority.value
            else:
                field = "blocker"
                value = request.blocker
            updated = conn.execute(
                f"""UPDATE football_brief.creator_revision_tasks
                    SET {field}=%s,updated_by_operator_id=%s,
                        lock_version=lock_version+1{timestamp_sql}
                    WHERE id=%s AND lock_version=%s RETURNING *""",
                (value,actor,task_id,request.expected_lock_version),
            ).fetchone()
            if not updated:
                raise ReviewWorkspaceError("revision_task_conflict")
            events = conn.execute(
                """SELECT * FROM football_brief.creator_revision_task_events
                   WHERE task_id=%s ORDER BY created_at,id""",
                (task_id,),
            ).fetchall()
        return {"ok": True, "task": dict(updated), "events": [dict(row) for row in events]}

    def compare(self, *, request: CompareTarget) -> dict[str, Any]:
        with self.database.connection() as conn:
            current = self._snapshot(conn, request.target_type, request.current_id)
            previous_id = request.previous_id or current.pop("_parent_id", None)
            previous = self._snapshot(conn, request.target_type, previous_id) if previous_id else None
        return {
            "ok": True,
            "target_type": request.target_type.value,
            "current": current,
            "previous": previous,
            "differences": self._differences(previous, current),
        }

    def _resolve_target(self, conn, target_type: ReviewTarget, target_id: UUID) -> dict[str, Any]:
        queries = {
            ReviewTarget.WORKFLOW_VERSION: """SELECT pw.portfolio_content_id
                FROM football_brief.production_workflow_versions x
                JOIN football_brief.production_workflows pw ON pw.id=x.workflow_id WHERE x.id=%s""",
            ReviewTarget.SCRIPT_VERSION: """SELECT sd.portfolio_content_id
                FROM football_brief.script_versions x
                JOIN football_brief.script_documents sd ON sd.id=x.script_document_id WHERE x.id=%s""",
            ReviewTarget.SCRIPT_SECTION: """SELECT sd.portfolio_content_id
                FROM football_brief.script_sections x
                JOIN football_brief.script_versions sv ON sv.id=x.script_version_id
                JOIN football_brief.script_documents sd ON sd.id=sv.script_document_id WHERE x.id=%s""",
            ReviewTarget.AUDIO_MIX_VERSION: """SELECT ap.portfolio_content_id
                FROM football_brief.audio_mix_versions x
                JOIN football_brief.audio_productions ap ON ap.id=x.audio_production_id WHERE x.id=%s""",
            ReviewTarget.AUDIO_PARAGRAPH: """SELECT ap.portfolio_content_id
                FROM football_brief.audio_paragraphs x
                JOIN football_brief.audio_productions ap ON ap.id=x.audio_production_id WHERE x.id=%s""",
            ReviewTarget.VISUAL_SHOT_VERSION: """SELECT vp.portfolio_content_id
                FROM football_brief.visual_shot_versions x
                JOIN football_brief.visual_shots vs ON vs.id=x.visual_shot_id
                JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id WHERE x.id=%s""",
            ReviewTarget.VISUAL_CANDIDATE: """SELECT vp.portfolio_content_id
                FROM football_brief.visual_candidates x
                JOIN football_brief.visual_shot_versions vsv ON vsv.id=x.visual_shot_version_id
                JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
                JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id WHERE x.id=%s""",
        }
        row = conn.execute(queries[target_type], (target_id,)).fetchone()
        if not row:
            raise ReviewWorkspaceError("review_target_not_found")
        return dict(row)

    def _snapshot(self, conn, target_type: ReviewTarget, target_id: UUID) -> dict[str, Any]:
        if target_type == ReviewTarget.WORKFLOW_VERSION:
            row = self._one(conn, "SELECT * FROM football_brief.production_workflow_versions WHERE id=%s", target_id)
            result = dict(row)
            result["_parent_id"] = result.get("parent_version_id")
            return result
        if target_type == ReviewTarget.SCRIPT_VERSION:
            row = self._one(conn, "SELECT * FROM football_brief.script_versions WHERE id=%s", target_id)
            result = dict(row)
            result["sections"] = [dict(item) for item in conn.execute(
                "SELECT * FROM football_brief.script_sections WHERE script_version_id=%s ORDER BY sequence", (target_id,)
            ).fetchall()]
            result["claims"] = [dict(item) for item in conn.execute(
                "SELECT * FROM football_brief.script_claims WHERE script_version_id=%s ORDER BY claim_key", (target_id,)
            ).fetchall()]
            result["sources"] = [dict(item) for item in conn.execute(
                "SELECT * FROM football_brief.script_sources WHERE script_version_id=%s ORDER BY source_key", (target_id,)
            ).fetchall()]
            result["_parent_id"] = result.get("parent_version_id")
            return result
        if target_type == ReviewTarget.SCRIPT_SECTION:
            return dict(self._one(conn, "SELECT * FROM football_brief.script_sections WHERE id=%s", target_id))
        if target_type == ReviewTarget.AUDIO_MIX_VERSION:
            row = self._one(conn, "SELECT * FROM football_brief.audio_mix_versions WHERE id=%s", target_id)
            result = dict(row)
            result["tracks"] = [dict(item) for item in conn.execute(
                "SELECT * FROM football_brief.audio_mix_tracks WHERE audio_mix_version_id=%s ORDER BY track_role,id", (target_id,)
            ).fetchall()]
            result["_parent_id"] = result.get("parent_mix_version_id")
            return result
        if target_type == ReviewTarget.AUDIO_PARAGRAPH:
            row = self._one(conn, "SELECT * FROM football_brief.audio_paragraphs WHERE id=%s", target_id)
            result = dict(row)
            result["takes"] = [dict(item) for item in conn.execute(
                "SELECT * FROM football_brief.audio_segment_takes WHERE paragraph_id=%s ORDER BY take_version", (target_id,)
            ).fetchall()]
            return result
        if target_type == ReviewTarget.VISUAL_SHOT_VERSION:
            row = self._one(conn, "SELECT * FROM football_brief.visual_shot_versions WHERE id=%s", target_id)
            result = dict(row)
            candidates = [dict(item) for item in conn.execute(
                "SELECT * FROM football_brief.visual_candidates WHERE visual_shot_version_id=%s ORDER BY ordinal", (target_id,)
            ).fetchall()]
            for candidate in candidates:
                candidate["checks"] = [dict(item) for item in conn.execute(
                    "SELECT * FROM football_brief.visual_candidate_checks WHERE visual_candidate_id=%s ORDER BY check_type",
                    (candidate["id"],),
                ).fetchall()]
            result["candidates"] = candidates
            result["_parent_id"] = result.get("parent_version_id")
            return result
        row = self._one(conn, "SELECT * FROM football_brief.visual_candidates WHERE id=%s", target_id)
        result = dict(row)
        result["checks"] = [dict(item) for item in conn.execute(
            "SELECT * FROM football_brief.visual_candidate_checks WHERE visual_candidate_id=%s ORDER BY check_type",
            (target_id,),
        ).fetchall()]
        return result

    @staticmethod
    def _one(conn, sql: str, target_id: UUID):
        row = conn.execute(sql, (target_id,)).fetchone()
        if not row:
            raise ReviewWorkspaceError("review_target_not_found")
        return row

    @staticmethod
    def _differences(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
        if previous is None:
            return [{"field": "version", "before": None, "after": "initial"}]
        ignored = {"id", "created_at", "updated_at", "submitted_at", "decided_at", "_parent_id"}
        changes: list[dict[str, Any]] = []
        for key in sorted(set(previous).union(current) - ignored):
            before = previous.get(key)
            after = current.get(key)
            if before != after:
                if isinstance(before, list) or isinstance(after, list):
                    changes.append({
                        "field": key,
                        "before_count": len(before or []),
                        "after_count": len(after or []),
                    })
                else:
                    changes.append({"field": key, "before": before, "after": after})
        return changes
