"""Database-backed production workflow with optimistic concurrency and immutable evidence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID, uuid4

from src.domain.production_workflow import (
    ProductionStage,
    REVIEW_STAGES,
    ReviewDecision,
    WorkflowRuleError,
    WorkflowStatus,
    WorkflowVersionStatus,
    compatibility_stage,
    reopen_plan,
    review_plan,
    submit_plan,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class ProductionWorkflowError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value or {})


class ProductionWorkflowService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def initialize(self, *, content_id: UUID, actor: str) -> dict[str, Any]:
        workflow_id = uuid4()
        version_id = uuid4()
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            content = conn.execute(
                """SELECT pc.*, mp.brand_id, b.slug AS brand_slug, b.display_name AS brand_name,
                          bp.id AS active_brand_profile_id, bp.version AS active_brand_profile_version
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   LEFT JOIN football_brief.brand_profiles bp
                     ON bp.brand_id=mp.brand_id AND bp.status='active'
                   WHERE pc.id=%s FOR UPDATE OF pc""",
                (content_id,),
            ).fetchone()
            if not content:
                raise ProductionWorkflowError("content_not_found")
            existing = conn.execute(
                "SELECT id FROM football_brief.production_workflows WHERE portfolio_content_id=%s",
                (content_id,),
            ).fetchone()
            if existing:
                return {"ok": True, "workflow_id": existing["id"], "already_exists": True}
            if content["active_brand_profile_id"] is None:
                raise ProductionWorkflowError("active_brand_profile_required")
            snapshot = {
                "content_id": str(content["id"]),
                "brand_id": str(content["brand_id"]),
                "brand_slug": str(content["brand_slug"]),
                "brand_profile_id": str(content["active_brand_profile_id"]),
                "brand_profile_version": int(content["active_brand_profile_version"]),
                "title": content["title"],
                "concept": content["concept"],
                "format": content["format"],
                "script": content["script"],
                "voiceover": content["voiceover"],
                "scene_plan": content["scene_plan"],
                "metadata": content["metadata"] or {},
            }
            conn.execute(
                """INSERT INTO football_brief.production_workflows
                   (id, portfolio_content_id, current_stage, status, current_version_id,
                    lock_version, created_by)
                   VALUES (%s,%s,'concept_draft','active',%s,1,%s)""",
                (workflow_id, content_id, version_id, actor),
            )
            conn.execute(
                """INSERT INTO football_brief.production_workflow_versions
                   (id, workflow_id, version, basis_content_version, status, snapshot,
                    created_by, last_edited_by)
                   VALUES (%s,%s,1,%s,'working',%s::jsonb,%s,%s)""",
                (version_id, workflow_id, content["version"], _json(snapshot), actor, actor),
            )
            self._history(
                conn,
                workflow_id=workflow_id,
                workflow_version_id=version_id,
                from_stage=None,
                to_stage=ProductionStage.CONCEPT_DRAFT,
                event="created",
                actor=actor,
                rationale="Detailed production workflow initialized",
                from_lock=0,
            )
        return {"ok": True, "workflow_id": workflow_id, "already_exists": False}

    def detail(self, *, workflow_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            workflow = conn.execute(
                """SELECT w.*, pc.title, pc.scheduled_for, pc.stage AS compatibility_stage,
                          pc.version AS content_version, mp.brand_id, b.slug AS brand_slug,
                          b.display_name AS brand_name, v.version AS workflow_version,
                          v.status AS version_status, v.snapshot, v.last_edited_by,
                          v.created_by AS version_created_by, v.basis_content_version
                   FROM football_brief.production_workflows w
                   JOIN football_brief.production_workflow_versions v ON v.id=w.current_version_id
                   JOIN football_brief.portfolio_content pc ON pc.id=w.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE w.id=%s""",
                (workflow_id,),
            ).fetchone()
            if not workflow:
                raise ProductionWorkflowError("workflow_not_found")
            versions = conn.execute(
                """SELECT * FROM football_brief.production_workflow_versions
                   WHERE workflow_id=%s ORDER BY version DESC""",
                (workflow_id,),
            ).fetchall()
            history = conn.execute(
                """SELECT * FROM football_brief.production_workflow_stage_history
                   WHERE workflow_id=%s ORDER BY created_at, id""",
                (workflow_id,),
            ).fetchall()
            assignments = conn.execute(
                """SELECT a.*, u.display_name AS assignee_name,
                          (a.active AND a.due_at IS NOT NULL AND a.due_at < now()) AS overdue
                   FROM football_brief.production_workflow_assignments a
                   JOIN football_brief.operator_users u ON u.operator_id=a.assignee_operator_id
                   WHERE a.workflow_id=%s ORDER BY a.created_at DESC""",
                (workflow_id,),
            ).fetchall()
            comments = conn.execute(
                """SELECT c.*, u.display_name AS author_name
                   FROM football_brief.production_workflow_comments c
                   JOIN football_brief.operator_users u ON u.operator_id=c.author_operator_id
                   JOIN football_brief.production_workflow_versions v ON v.id=c.workflow_version_id
                   WHERE v.workflow_id=%s ORDER BY c.created_at, c.id""",
                (workflow_id,),
            ).fetchall()
            decisions = conn.execute(
                """SELECT d.*, u.display_name AS reviewer_name
                   FROM football_brief.production_workflow_decisions d
                   JOIN football_brief.operator_users u ON u.operator_id=d.reviewer_operator_id
                   WHERE d.workflow_id=%s ORDER BY d.created_at, d.id""",
                (workflow_id,),
            ).fetchall()
        return {
            "ok": True,
            "workflow": dict(workflow),
            "versions": [dict(row) for row in versions],
            "history": [dict(row) for row in history],
            "assignments": [dict(row) for row in assignments],
            "comments": [dict(row) for row in comments],
            "decisions": [dict(row) for row in decisions],
        }

    def workflow_for_content(self, *, content_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT id FROM football_brief.production_workflows WHERE portfolio_content_id=%s",
                (content_id,),
            ).fetchone()
        if not row:
            raise ProductionWorkflowError("workflow_not_found")
        return self.detail(workflow_id=row["id"])

    def update_snapshot(
        self,
        *,
        workflow_id: UUID,
        expected_lock_version: int,
        patch: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        if not patch:
            raise ProductionWorkflowError("snapshot_patch_required")
        protected = {"content_id", "brand_id", "brand_slug", "brand_profile_id", "brand_profile_version"}
        invalid = sorted(protected.intersection(patch))
        if invalid:
            raise ProductionWorkflowError("protected_snapshot_fields", details={"fields": invalid})
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, workflow_id, expected_lock_version)
            if row["workflow_status"] != WorkflowStatus.ACTIVE.value:
                raise ProductionWorkflowError("workflow_not_active")
            if row["version_status"] != WorkflowVersionStatus.WORKING.value:
                raise ProductionWorkflowError("version_not_working")
            if ProductionStage(row["current_stage"]) in REVIEW_STAGES:
                raise ProductionWorkflowError("review_snapshot_is_sealed")
            snapshot = _dict(row["snapshot"])
            snapshot.update(patch)
            conn.execute(
                """UPDATE football_brief.production_workflow_versions
                   SET snapshot=%s::jsonb, last_edited_by=%s
                   WHERE id=%s""",
                (_json(snapshot), actor, row["current_version_id"]),
            )
            self._advance_lock(
                conn,
                workflow_id=workflow_id,
                expected_lock=expected_lock_version,
            )
            self._history(
                conn,
                workflow_id=workflow_id,
                workflow_version_id=row["current_version_id"],
                from_stage=ProductionStage(row["current_stage"]),
                to_stage=ProductionStage(row["current_stage"]),
                event="snapshot_updated",
                actor=actor,
                rationale="Working snapshot updated",
                from_lock=expected_lock_version,
            )
        return self.detail(workflow_id=workflow_id)

    def submit(
        self,
        *,
        workflow_id: UUID,
        expected_lock_version: int,
        actor: str,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, workflow_id, expected_lock_version)
            try:
                plan = submit_plan(
                    stage=row["current_stage"],
                    workflow_status=row["workflow_status"],
                    version_status=row["version_status"],
                    snapshot=_dict(row["snapshot"]),
                )
            except WorkflowRuleError as exc:
                raise ProductionWorkflowError(exc.code, details=exc.details) from exc
            submitted_at = "now()" if plan.version_status == WorkflowVersionStatus.IN_REVIEW else "submitted_at"
            conn.execute(
                f"""UPDATE football_brief.production_workflow_versions
                    SET status=%s, submitted_at={submitted_at}
                    WHERE id=%s""",
                (plan.version_status.value, row["current_version_id"]),
            )
            self._complete_assignment(conn, row)
            self._update_workflow(
                conn,
                workflow_id=workflow_id,
                expected_lock=expected_lock_version,
                current_stage=plan.to_stage,
                status=plan.workflow_status,
                current_version_id=row["current_version_id"],
            )
            self._project_content(conn, row["portfolio_content_id"], plan.to_stage, plan.workflow_status)
            self._history(
                conn,
                workflow_id=workflow_id,
                workflow_version_id=row["current_version_id"],
                from_stage=plan.from_stage,
                to_stage=plan.to_stage,
                event="submitted",
                actor=actor,
                rationale=rationale or "Stage work submitted",
                from_lock=expected_lock_version,
            )
        return self.detail(workflow_id=workflow_id)

    def decide(
        self,
        *,
        workflow_id: UUID,
        expected_lock_version: int,
        reviewer: str,
        decision: ReviewDecision | str,
        rationale: str,
    ) -> dict[str, Any]:
        if len(rationale.strip()) < 3:
            raise ProductionWorkflowError("review_rationale_required")
        selected = ReviewDecision(decision)
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            row = self._locked(conn, workflow_id, expected_lock_version)
            try:
                plan = review_plan(
                    stage=row["current_stage"],
                    workflow_status=row["workflow_status"],
                    version_status=row["version_status"],
                    decision=selected,
                    snapshot=_dict(row["snapshot"]),
                    reviewer=reviewer,
                    last_edited_by=row["last_edited_by"],
                )
            except WorkflowRuleError as exc:
                raise ProductionWorkflowError(exc.code, details=exc.details) from exc
            conn.execute(
                """INSERT INTO football_brief.production_workflow_decisions
                   (workflow_id, workflow_version_id, stage, decision, reviewer_operator_id,
                    rationale, workflow_lock_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    workflow_id,
                    row["current_version_id"],
                    plan.from_stage.value,
                    selected.value,
                    reviewer,
                    rationale,
                    expected_lock_version,
                ),
            )
            self._complete_assignment(conn, row)
            event = selected.value
            history_version_id = row["current_version_id"]
            if selected == ReviewDecision.APPROVED:
                conn.execute(
                    """UPDATE football_brief.production_workflow_versions
                       SET status='approved', decided_at=now()
                       WHERE id=%s""",
                    (row["current_version_id"],),
                )
                next_version_id = row["current_version_id"]
                if plan.create_successor:
                    next_version_id = self._insert_successor(
                        conn,
                        row=row,
                        actor=reviewer,
                        status=WorkflowVersionStatus.WORKING,
                        reason=f"Approved {plan.from_stage.value}",
                        increment_content_version=False,
                    )
                self._update_workflow(
                    conn,
                    workflow_id=workflow_id,
                    expected_lock=expected_lock_version,
                    current_stage=plan.to_stage,
                    status=plan.workflow_status,
                    current_version_id=next_version_id,
                    completed=plan.complete_workflow,
                )
                event = "completed" if plan.complete_workflow else "approved"
            elif selected == ReviewDecision.CHANGES_REQUESTED:
                conn.execute(
                    """UPDATE football_brief.production_workflow_versions
                       SET status='changes_requested', decided_at=now()
                       WHERE id=%s""",
                    (row["current_version_id"],),
                )
                next_version_id = self._insert_successor(
                    conn,
                    row=row,
                    actor=reviewer,
                    status=WorkflowVersionStatus.WORKING,
                    reason=rationale,
                    increment_content_version=True,
                )
                self._update_workflow(
                    conn,
                    workflow_id=workflow_id,
                    expected_lock=expected_lock_version,
                    current_stage=plan.to_stage,
                    status=WorkflowStatus.ACTIVE,
                    current_version_id=next_version_id,
                )
            else:
                conn.execute(
                    """UPDATE football_brief.production_workflow_versions
                       SET status='rejected', decided_at=now()
                       WHERE id=%s""",
                    (row["current_version_id"],),
                )
                self._update_workflow(
                    conn,
                    workflow_id=workflow_id,
                    expected_lock=expected_lock_version,
                    current_stage=plan.to_stage,
                    status=WorkflowStatus.BLOCKED,
                    current_version_id=row["current_version_id"],
                    blocked_reason=rationale,
                )
            self._project_content(conn, row["portfolio_content_id"], plan.to_stage, plan.workflow_status)
            self._history(
                conn,
                workflow_id=workflow_id,
                workflow_version_id=history_version_id,
                from_stage=plan.from_stage,
                to_stage=plan.to_stage,
                event=event,
                actor=reviewer,
                rationale=rationale,
                from_lock=expected_lock_version,
            )
        return self.detail(workflow_id=workflow_id)

    def reopen(
        self,
        *,
        workflow_id: UUID,
        expected_lock_version: int,
        actor: str,
        rationale: str,
    ) -> dict[str, Any]:
        if len(rationale.strip()) < 3:
            raise ProductionWorkflowError("reopen_rationale_required")
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, workflow_id, expected_lock_version)
            try:
                plan = reopen_plan(
                    stage=row["current_stage"],
                    workflow_status=row["workflow_status"],
                    version_status=row["version_status"],
                )
            except WorkflowRuleError as exc:
                raise ProductionWorkflowError(exc.code, details=exc.details) from exc
            next_version_id = self._insert_successor(
                conn,
                row=row,
                actor=actor,
                status=WorkflowVersionStatus.WORKING,
                reason=rationale,
                increment_content_version=True,
            )
            self._update_workflow(
                conn,
                workflow_id=workflow_id,
                expected_lock=expected_lock_version,
                current_stage=plan.to_stage,
                status=WorkflowStatus.ACTIVE,
                current_version_id=next_version_id,
            )
            self._project_content(conn, row["portfolio_content_id"], plan.to_stage, WorkflowStatus.ACTIVE)
            self._history(
                conn,
                workflow_id=workflow_id,
                workflow_version_id=next_version_id,
                from_stage=plan.from_stage,
                to_stage=plan.to_stage,
                event="reopened",
                actor=actor,
                rationale=rationale,
                from_lock=expected_lock_version,
            )
        return self.detail(workflow_id=workflow_id)

    def assign(
        self,
        *,
        workflow_id: UUID,
        expected_lock_version: int,
        assignee: str,
        actor: str,
        due_at: datetime | None = None,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, workflow_id, expected_lock_version)
            if row["workflow_status"] != WorkflowStatus.ACTIVE.value:
                raise ProductionWorkflowError("workflow_not_active")
            self._validate_assignee(
                conn,
                assignee=assignee,
                stage=ProductionStage(row["current_stage"]),
                brand_id=row["brand_id"],
            )
            conn.execute(
                """UPDATE football_brief.production_workflow_assignments
                   SET active=false
                   WHERE workflow_id=%s AND workflow_version_id=%s AND stage=%s AND active=true""",
                (workflow_id, row["current_version_id"], row["current_stage"]),
            )
            assignment = conn.execute(
                """INSERT INTO football_brief.production_workflow_assignments
                   (workflow_id, workflow_version_id, stage, assignee_operator_id,
                    assigned_by, due_at)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    workflow_id,
                    row["current_version_id"],
                    row["current_stage"],
                    assignee,
                    actor,
                    due_at,
                ),
            ).fetchone()
            self._advance_lock(conn, workflow_id=workflow_id, expected_lock=expected_lock_version)
            self._history(
                conn,
                workflow_id=workflow_id,
                workflow_version_id=row["current_version_id"],
                from_stage=ProductionStage(row["current_stage"]),
                to_stage=ProductionStage(row["current_stage"]),
                event="assignment_changed",
                actor=actor,
                rationale=f"Assigned to {assignee}",
                from_lock=expected_lock_version,
            )
        return {"ok": True, "assignment": dict(assignment), "workflow": self.detail(workflow_id=workflow_id)["workflow"]}

    def add_comment(
        self,
        *,
        workflow_id: UUID,
        workflow_version_id: UUID,
        stage: ProductionStage | str,
        actor: str,
        body: str,
        comment_type: str = "general",
        parent_comment_id: UUID | None = None,
    ) -> dict[str, Any]:
        if not body.strip():
            raise ProductionWorkflowError("comment_body_required")
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            version = conn.execute(
                """SELECT id FROM football_brief.production_workflow_versions
                   WHERE id=%s AND workflow_id=%s""",
                (workflow_version_id, workflow_id),
            ).fetchone()
            if not version:
                raise ProductionWorkflowError("workflow_version_not_found")
            if parent_comment_id is not None:
                parent = conn.execute(
                    """SELECT id FROM football_brief.production_workflow_comments
                       WHERE id=%s AND workflow_version_id=%s""",
                    (parent_comment_id, workflow_version_id),
                ).fetchone()
                if not parent:
                    raise ProductionWorkflowError("parent_comment_not_found")
            comment = conn.execute(
                """INSERT INTO football_brief.production_workflow_comments
                   (workflow_version_id, stage, author_operator_id, comment_type, body, parent_comment_id)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (workflow_version_id, ProductionStage(stage).value, actor, comment_type, body, parent_comment_id),
            ).fetchone()
        return {"ok": True, "comment": dict(comment)}

    def resolve_comment(self, *, comment_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            comment = conn.execute(
                """UPDATE football_brief.production_workflow_comments
                   SET resolved_by_operator_id=%s, resolved_at=now()
                   WHERE id=%s AND resolved_at IS NULL RETURNING *""",
                (actor, comment_id),
            ).fetchone()
            if not comment:
                raise ProductionWorkflowError("comment_not_found_or_already_resolved")
        return {"ok": True, "comment": dict(comment)}

    def queue(
        self,
        *,
        brand_ids: Iterable[UUID | str] | None = None,
        stage: ProductionStage | str | None = None,
        status: WorkflowStatus | str | None = None,
        assignee: str | None = None,
        overdue: bool | None = None,
        blocked: bool | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["b.active=true"]
        values: list[Any] = []
        scoped = [str(value) for value in brand_ids or []]
        if brand_ids is not None:
            if not scoped:
                return []
            conditions.append("mp.brand_id = ANY(%s::uuid[])")
            values.append(scoped)
        if stage is not None:
            conditions.append("w.current_stage=%s")
            values.append(ProductionStage(stage).value)
        if status is not None:
            conditions.append("w.status=%s")
            values.append(WorkflowStatus(status).value)
        if assignee:
            conditions.append("a.assignee_operator_id=%s")
            values.append(assignee)
        if overdue is True:
            conditions.append("a.active=true AND a.due_at IS NOT NULL AND a.due_at < now()")
        elif overdue is False:
            conditions.append("NOT (a.active=true AND a.due_at IS NOT NULL AND a.due_at < now())")
        if blocked is True:
            conditions.append("w.status='blocked'")
        elif blocked is False:
            conditions.append("w.status<>'blocked'")
        sql = f"""SELECT w.*, pc.title, pc.scheduled_for, pc.stage AS compatibility_stage,
                         mp.brand_id, b.slug AS brand_slug, b.display_name AS brand_name,
                         v.version AS workflow_version, v.status AS version_status,
                         v.last_edited_by, a.assignee_operator_id, a.due_at,
                         (a.active AND a.due_at IS NOT NULL AND a.due_at < now()) AS overdue
                  FROM football_brief.production_workflows w
                  JOIN football_brief.production_workflow_versions v ON v.id=w.current_version_id
                  JOIN football_brief.portfolio_content pc ON pc.id=w.portfolio_content_id
                  JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                  JOIN football_brief.brands b ON b.id=mp.brand_id
                  LEFT JOIN football_brief.production_workflow_assignments a
                    ON a.workflow_id=w.id AND a.workflow_version_id=w.current_version_id
                   AND a.stage=w.current_stage AND a.active=true
                  WHERE {' AND '.join(conditions)}
                  ORDER BY (a.due_at IS NOT NULL AND a.due_at < now()) DESC,
                           a.due_at NULLS LAST, pc.scheduled_for, b.display_name"""
        with self.database.connection() as conn:
            rows = conn.execute(sql, tuple(values)).fetchall()
        return [dict(row) for row in rows]

    def _locked(self, conn, workflow_id: UUID, expected_lock_version: int):
        row = conn.execute(
            """SELECT w.id, w.portfolio_content_id, w.current_stage,
                      w.status AS workflow_status, w.current_version_id, w.lock_version,
                      w.blocked_reason, v.version AS workflow_version,
                      v.status AS version_status, v.snapshot, v.last_edited_by,
                      v.basis_content_version, pc.version AS content_version,
                      mp.brand_id
               FROM football_brief.production_workflows w
               JOIN football_brief.production_workflow_versions v ON v.id=w.current_version_id
               JOIN football_brief.portfolio_content pc ON pc.id=w.portfolio_content_id
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               WHERE w.id=%s FOR UPDATE OF w, v, pc""",
            (workflow_id,),
        ).fetchone()
        if not row:
            raise ProductionWorkflowError("workflow_not_found")
        if int(row["lock_version"]) != int(expected_lock_version):
            raise ProductionWorkflowError(
                "workflow_conflict",
                details={"expected": expected_lock_version, "actual": int(row["lock_version"])},
            )
        return row

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        operator = conn.execute(
            "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
            (operator_id,),
        ).fetchone()
        if not operator:
            raise ProductionWorkflowError("operator_inactive_or_missing")

    @staticmethod
    def _validate_assignee(conn, *, assignee: str, stage: ProductionStage, brand_id: UUID) -> None:
        operator = conn.execute(
            "SELECT id, active FROM football_brief.operator_users WHERE operator_id=%s",
            (assignee,),
        ).fetchone()
        if not operator or not operator["active"]:
            raise ProductionWorkflowError("assignee_inactive_or_missing")
        roles = {
            str(row["role"])
            for row in conn.execute(
                "SELECT role FROM football_brief.operator_user_roles WHERE operator_user_id=%s",
                (operator["id"],),
            ).fetchall()
        }
        if "admin" not in roles:
            required = "publisher" if stage in {ProductionStage.SCHEDULING, ProductionStage.PUBLICATION} else (
                "reviewer" if stage in REVIEW_STAGES else "producer"
            )
            if required not in roles:
                raise ProductionWorkflowError("assignee_role_mismatch", details={"required_role": required})
            assigned = conn.execute(
                """SELECT 1 FROM football_brief.operator_brand_assignments
                   WHERE operator_user_id=%s AND brand_id=%s""",
                (operator["id"], brand_id),
            ).fetchone()
            if not assigned:
                raise ProductionWorkflowError("assignee_brand_access_denied")

    @staticmethod
    def _advance_lock(conn, *, workflow_id: UUID, expected_lock: int) -> None:
        updated = conn.execute(
            """UPDATE football_brief.production_workflows
               SET lock_version=lock_version+1
               WHERE id=%s AND lock_version=%s RETURNING id""",
            (workflow_id, expected_lock),
        ).fetchone()
        if not updated:
            raise ProductionWorkflowError("workflow_conflict")

    @staticmethod
    def _update_workflow(
        conn,
        *,
        workflow_id: UUID,
        expected_lock: int,
        current_stage: ProductionStage,
        status: WorkflowStatus,
        current_version_id: UUID,
        blocked_reason: str | None = None,
        completed: bool = False,
    ) -> None:
        updated = conn.execute(
            """UPDATE football_brief.production_workflows
               SET current_stage=%s, status=%s, current_version_id=%s,
                   blocked_reason=%s, completed_at=CASE WHEN %s THEN now() ELSE NULL END,
                   lock_version=lock_version+1
               WHERE id=%s AND lock_version=%s RETURNING id""",
            (
                current_stage.value,
                status.value,
                current_version_id,
                blocked_reason,
                completed,
                workflow_id,
                expected_lock,
            ),
        ).fetchone()
        if not updated:
            raise ProductionWorkflowError("workflow_conflict")

    @staticmethod
    def _project_content(conn, content_id: UUID, stage: ProductionStage, status: WorkflowStatus) -> None:
        conn.execute(
            "UPDATE football_brief.portfolio_content SET stage=%s WHERE id=%s",
            (compatibility_stage(stage, status), content_id),
        )

    @staticmethod
    def _complete_assignment(conn, row) -> None:
        conn.execute(
            """UPDATE football_brief.production_workflow_assignments
               SET active=false, completed_at=now()
               WHERE workflow_id=%s AND workflow_version_id=%s
                 AND stage=%s AND active=true""",
            (row["id"], row["current_version_id"], row["current_stage"]),
        )

    @staticmethod
    def _history(
        conn,
        *,
        workflow_id: UUID,
        workflow_version_id: UUID,
        from_stage: ProductionStage | None,
        to_stage: ProductionStage,
        event: str,
        actor: str,
        rationale: str | None,
        from_lock: int,
    ) -> None:
        conn.execute(
            """INSERT INTO football_brief.production_workflow_stage_history
               (workflow_id, workflow_version_id, from_stage, to_stage, event,
                actor, rationale, from_lock_version, to_lock_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                workflow_id,
                workflow_version_id,
                from_stage.value if from_stage is not None else None,
                to_stage.value,
                event,
                actor,
                rationale,
                from_lock,
                from_lock + 1,
            ),
        )

    def _insert_successor(
        self,
        conn,
        *,
        row,
        actor: str,
        status: WorkflowVersionStatus,
        reason: str,
        increment_content_version: bool,
    ) -> UUID:
        next_content_version = int(row["content_version"])
        if increment_content_version:
            content = conn.execute(
                """UPDATE football_brief.portfolio_content
                   SET version=version+1 WHERE id=%s RETURNING version""",
                (row["portfolio_content_id"],),
            ).fetchone()
            next_content_version = int(content["version"])
        next_id = uuid4()
        conn.execute(
            """INSERT INTO football_brief.production_workflow_versions
               (id, workflow_id, version, parent_version_id, basis_content_version,
                status, revision_reason, snapshot, created_by, last_edited_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (
                next_id,
                row["id"],
                int(row["workflow_version"]) + 1,
                row["current_version_id"],
                next_content_version,
                status.value,
                reason,
                _json(_dict(row["snapshot"])),
                actor,
                row["last_edited_by"],
            ),
        )
        return next_id
